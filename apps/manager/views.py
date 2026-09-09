import posixpath
import shutil
import traceback
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.utils import timezone
import os
from SongPoetry import settings
from apps.visualization.models import ci, ciauthor
from apps.sushi_qa.models import UserDialogue
from django.http.multipartparser import TooManyFilesSent
import json
from .graphrag_import import run_graphrag_import  # 用相对路径
from apps.sushi_qa.qa_service import qa_service

# 获取自定义User模型
User = get_user_model()


def is_admin(user):
    """
    校验是否为管理员：
    1. 基于自定义User模型的 user_type=1（管理员标识）
    2. 兼容Django内置is_active（账号是否启用）
    """
    return user.is_authenticated and user.is_active and user.user_type == 1


def admin_required(view_func):
    """
    自定义管理员权限装饰器：
    - 未登录 → 跳管理员登录页
    - 已登录但非管理员 → 403权限拒绝
    """

    def _wrapped_view(request, *args, **kwargs):
        # 1. 检查是否登录（依赖Django内置认证的request.user）
        if not request.user.is_authenticated:
            # 记录当前访问地址，登录后可跳转回原页面（优化用户体验）
            request.session['next_url'] = request.get_full_path()
            return redirect(reverse('accounts:admin_login'))  # 跳管理员登录页（需确保accounts的urls命名正确）

        # 2. 检查是否为管理员
        if not is_admin(request.user):
            raise PermissionDenied("您没有管理员权限，无法访问此页面")

        # 3. 有权限 → 执行原视图
        return view_func(request, *args, **kwargs)

    return _wrapped_view


@admin_required  # 使用统一的管理员权限装饰器
def manage_home(request):
    """管理员首页：仅管理员可访问，显示基础统计数据"""
    # 可选：添加统计数据（增强首页功能）
    user_count = User.objects.count()
    poem_count = ci.objects.count()
    author_count = ciauthor.objects.count()
    dialogue_count = UserDialogue.objects.count()

    context = {
        'admin_name': request.user.username,  # 当前管理员用户名
        'stats': {
            'user_count': user_count,
            'poem_count': poem_count,
            'author_count': author_count,
            'dialogue_count': dialogue_count
        }
    }
    return render(request, 'manager/manager_home.html', context)


@admin_required
def user_list(request):
    """用户列表 + 筛选搜索（仅管理员可访问）"""
    q = request.GET.get("q", "").strip()
    user_type = request.GET.get("user_type", "")

    users = User.objects.all().order_by("-created_at")

    # 筛选逻辑
    if q:
        users = users.filter(username__icontains=q)
    if user_type.isdigit():  # 确保user_type是数字
        users = users.filter(user_type=int(user_type))

    # 分页处理
    paginator = Paginator(users, 50)  # 每页50条
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "users": page_obj,
        "q": q,
        "user_type": user_type,
    }
    return render(request, "manager/user_list.html", context)


@admin_required
def user_create(request):
    """创建新用户（仅管理员可访问）"""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        user_type = request.POST.get("user_type", "0")

        # 基础校验
        if not username or not email or not password:
            messages.error(request, "用户名、邮箱和密码不能为空")
            return redirect("manager:user_create")
        if User.objects.filter(username=username).exists():
            messages.error(request, "该用户名已存在")
            return redirect("manager:user_create")
        if not user_type.isdigit():
            user_type = 0  # 默认普通用户

        # 创建用户（使用Django内置create_user，自动加密密码）
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            user_type=int(user_type),
            created_at=timezone.now()  # 若模型有创建时间字段，需手动赋值
        )
        messages.success(request, "用户创建成功！")
        return redirect("manager:user_list")

    return render(request, "manager/user_form.html")


@admin_required
def user_detail(request, pk):
    """用户详情（仅管理员可访问）"""
    user = get_object_or_404(User, pk=pk)
    return render(request, 'manager/user_detail.html', {'user': user})


# 编辑用户
@admin_required
def user_edit(request, pk):
    """编辑用户"""
    user = get_object_or_404(User, id=pk)
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        user_type = request.POST.get("user_type")

        try:
            user_type = int(user_type)
        except (ValueError, TypeError):
            user_type = 0

        user.username = username
        user.email = email
        user.user_type = user_type

        if password:  # 若填写新密码
            user.set_password(password)

        user.save()
        messages.success(request, "用户信息已更新")
        return redirect("manager:user_list")

    return render(request, "manager/user_form.html", {"edit_user": user})


@admin_required
def user_delete(request, pk):
    """删除用户（仅管理员可访问）"""
    user = get_object_or_404(User, id=pk)
    # 禁止删除当前登录的管理员（防止误删自己）
    if user.id == request.user.id:
        messages.error(request, "无法删除当前登录的管理员账号")
        return redirect("manager:user_list")
    user.delete()
    messages.success(request, "用户已删除")
    return redirect("manager:user_list")


@admin_required
def poem_list(request):
    """词作列表 + 检索（仅管理员可访问）"""
    q = request.GET.get("q", "").strip()
    rhythmic = request.GET.get("rhythmic", "").strip()

    poems = ci.objects.all().order_by("value")
    if q:
        poems = poems.filter(content__icontains=q)
    if rhythmic:
        poems = poems.filter(rhythmic__icontains=rhythmic)

    paginator = Paginator(poems, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, "manager/poem_list.html", {
        "poems": page_obj,
        "q": q,
        "rhythmic": rhythmic
    })


@admin_required
def poem_create(request):
    """添加词作（仅管理员可访问）"""
    if request.method == 'POST':
        rhythmic = request.POST.get('rhythmic', "").strip()
        author = request.POST.get('author', "").strip()
        content = request.POST.get('content', "").strip()

        if not rhythmic or not author or not content:
            messages.error(request, "词牌名、作者和内容不能为空")
            return redirect('manager:poem_create')

        ci.objects.create(
            rhythmic=rhythmic,
            author=author,
            content=content
        )
        messages.success(request, "词作已添加成功！")
        return redirect('manager:poem_list')

    return render(request, 'manager/poem_form.html', {'title': '添加词作'})


@admin_required
def poem_detail(request, pk):
    """词作详情（仅管理员可访问）"""
    poem = get_object_or_404(ci, value=pk)
    return render(request, 'manager/poem_detail.html', {'poem': poem})


@admin_required
def poem_edit(request, pk):
    """编辑词作（仅管理员可访问）"""
    poem = get_object_or_404(ci, pk=pk)
    if request.method == 'POST':
        rhythmic = request.POST.get('rhythmic', "").strip()
        author = request.POST.get('author', "").strip()
        content = request.POST.get('content', "").strip()

        if not rhythmic or not author or not content:
            messages.error(request, "词牌名、作者和内容不能为空")
            return redirect('manager:poem_edit', pk=pk)

        poem.rhythmic = rhythmic
        poem.author = author
        poem.content = content
        poem.save()
        messages.success(request, "词作信息已更新！")
        return redirect('manager:poem_list')

    return render(request, 'manager/poem_form.html', {'title': '编辑词作', 'poem': poem})


@admin_required
def poem_delete(request, pk):
    """删除词作（仅管理员可访问）"""
    poem = get_object_or_404(ci, pk=pk)
    poem.delete()
    messages.warning(request, "词作已删除！")
    return redirect('manager:poem_list')


@admin_required
def author_list(request):
    """词人列表 + 检索（仅管理员可访问）"""
    q = request.GET.get("q", "").strip()
    authors = ciauthor.objects.all().order_by("value")
    if q:
        authors = authors.filter(name__icontains=q)

    paginator = Paginator(authors, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, "manager/author_list.html", {"authors": page_obj, "q": q})


@admin_required
def author_detail(request, pk):
    """词人详情（仅管理员可访问）"""
    author = get_object_or_404(ciauthor, value=pk)
    return render(request, 'manager/author_detail.html', {'author': author})


@admin_required
def author_create(request):
    """新增词人（仅管理员可访问）"""
    if request.method == 'POST':
        name = request.POST.get('name', "").strip()
        long_desc = request.POST.get('long_desc', "").strip()
        short_desc = request.POST.get('short_desc', "").strip()

        if not name or not short_desc:
            messages.error(request, "词人姓名和简介不能为空")
            return redirect('manager:author_create')

        ciauthor.objects.create(
            name=name,
            long_desc=long_desc,
            short_desc=short_desc
        )
        messages.success(request, "词人已添加成功！")
        return redirect('manager:author_list')

    return render(request, 'manager/author_form.html')


@admin_required
def author_edit(request, pk):
    """编辑词人（仅管理员可访问）"""
    author = get_object_or_404(ciauthor, value=pk)
    if request.method == 'POST':
        name = request.POST.get('name', "").strip()
        long_desc = request.POST.get('long_desc', "").strip()
        short_desc = request.POST.get('short_desc', "").strip()

        if not name or not short_desc:
            messages.error(request, "词人姓名和简介不能为空")
            return redirect('manager:author_edit', pk=pk)

        author.name = name
        author.long_desc = long_desc
        author.short_desc = short_desc
        author.save()
        messages.success(request, "词人信息已更新！")
        return redirect('manager:author_list')

    return render(request, 'manager/author_form.html', {'author': author})


@admin_required
def author_delete(request, pk):
    """删除词人（仅管理员可访问）"""
    author = get_object_or_404(ciauthor, value=pk)
    author.delete()
    messages.warning(request, "词人已删除！")
    return redirect('manager:author_list')


@admin_required
def dialogue_list(request):
    """对话列表 + 检索（仅管理员可访问）"""
    q = request.GET.get("q", "").strip()
    dialogues = UserDialogue.objects.all().order_by("-create_time")

    if q:
        dialogues = dialogues.filter(question__icontains=q)

    paginator = Paginator(dialogues, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, "manager/dialogue_list.html", {"dialogues": page_obj, "q": q})


@admin_required
def dialogue_detail(request, pk):
    """对话详情（仅管理员可访问）"""
    dialogue = get_object_or_404(UserDialogue, id=pk)
    return render(request, "manager/dialogue_detail.html", {"dialogue": dialogue})


@admin_required
def dialogue_create(request):
    """创建对话（仅管理员可访问）"""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        question = request.POST.get("question", "").strip()
        answer = request.POST.get("answer", "").strip()

        if not username or not question or not answer:
            messages.error(request, "用户名、问题和回答不能为空")
            return redirect("manager:dialogue_create")

        # 绑定已有用户（若不存在则创建匿名关联）
        user = User.objects.filter(username=username).first()

        UserDialogue.objects.create(
            user=user,
            username=username,
            question=question,
            answer=answer,
            create_time=timezone.now()  # 若模型无自动时间字段，需手动赋值
        )
        messages.success(request, "对话已创建成功！")
        return redirect("manager:dialogue_list")

    return render(request, "manager/dialogue_form.html")


@admin_required
def dialogue_edit(request, pk):
    """编辑对话（仅管理员可访问）"""
    dialogue = get_object_or_404(UserDialogue, id=pk)
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        question = request.POST.get("question", "").strip()
        answer = request.POST.get("answer", "").strip()

        if not username or not question or not answer:
            messages.error(request, "用户名、问题和回答不能为空")
            return redirect("manager:dialogue_edit", pk=pk)

        # 同步更新关联用户（若用户名变更）
        user = User.objects.filter(username=username).first()

        dialogue.user = user
        dialogue.username = username
        dialogue.question = question
        dialogue.answer = answer
        dialogue.update_time = timezone.now()  # 若模型有更新时间字段，需手动赋值
        dialogue.save()

        messages.success(request, "对话信息已更新！")
        return redirect("manager:dialogue_list")

    return render(request, "manager/dialogue_form.html", {"dialogue": dialogue})


@admin_required
def dialogue_delete(request, pk):
    """删除对话（仅管理员可访问）"""
    dialogue = get_object_or_404(UserDialogue, id=pk)
    dialogue.delete()
    messages.warning(request, "对话已删除！")
    return redirect("manager:dialogue_list")


@admin_required
def folder_upload(request):
    """处理文件夹上传"""
    if request.method == 'POST':
        try:
            # 1. 获取前端传递的所有数据
            files = request.FILES.getlist('folder_files')
            upload_desc = request.POST.get('upload_desc', '')
            file_paths_json = request.POST.get('file_relative_paths', '[]')

            try:
                file_relative_paths = json.loads(file_paths_json)
            except json.JSONDecodeError:
                file_relative_paths = []
                messages.warning(request, '文件路径解析失败，使用默认路径！')

            # 2. 基础校验
            if not files:
                messages.error(request, '请选择要上传的文件！')
                return redirect('manager:manager_home')

            if len(file_relative_paths) == 0:
                # 如果没有路径参数，直接用文件名作为路径
                file_relative_paths = [f.name for f in files]
            elif len(files) != len(file_relative_paths):
                messages.warning(request, '文件数量与路径数量不匹配，使用文件名作为路径！')
                file_relative_paths = [f.name for f in files]

            # 3. 定义上传根目录
            upload_root = settings.MEDIA_ROOT
            os.makedirs(upload_root, exist_ok=True)

            # 4. 限制单次上传文件数量
            max_files = getattr(settings, 'DATA_UPLOAD_MAX_NUMBER_FILES', 10000)
            if len(files) > max_files:
                messages.error(request, f'单次上传文件数量不能超过 {max_files} 个！本次选择了 {len(files)} 个')
                return redirect('manager:manager_home')

            # 5. 选择性清空目录（保留artifacts目录）
            preserve_dirs = ['artifacts']
            if os.path.abspath(upload_root).startswith(os.path.abspath(settings.BASE_DIR)):
                # ========== 增加目录存在检查 ==========
                if os.path.exists(upload_root):
                    for item in os.listdir(upload_root):
                        item_path = os.path.join(upload_root, item)
                        if item in preserve_dirs:
                            continue
                        try:
                            if os.path.isfile(item_path) or os.path.islink(item_path):
                                os.unlink(item_path)
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                        except Exception as e:
                            messages.warning(request, f'清理旧文件失败：{item} - {str(e)}')
                messages.info(request, f'已清空media目录下的业务文件（保留{preserve_dirs}目录）：{upload_root}')
            else:
                messages.error(request, '非法路径！禁止操作')
                return redirect('manager:manager_home')

            # 6. 遍历文件，按真实路径保存
            saved_count = 0
            artifacts_dir = os.path.join(upload_root, 'artifacts')  # 新增：定义artifacts目录
            os.makedirs(artifacts_dir, exist_ok=True)  # 确保目录存在

            for idx, file in enumerate(files):
                # ========== 优先保存到artifacts目录（适配parquet文件） ==========
                # 只处理parquet文件，其他文件按原逻辑保存
                if file.name.lower().endswith('.parquet'):
                    # parquet文件直接保存到artifacts目录
                    save_path = os.path.join(artifacts_dir, file.name)
                else:
                    # 其他文件按原路径保存
                    relative_path = file_relative_paths[idx]
                    relative_path = posixpath.normpath(relative_path)
                    save_path = os.path.join(upload_root, relative_path)
                    save_dir = os.path.dirname(save_path)
                    os.makedirs(save_dir, exist_ok=True)

                # ========== 增加文件写入容错 ==========
                try:
                    # 分块写入文件（支持大文件）
                    with open(save_path, 'wb') as f:
                        for chunk in file.chunks(chunk_size=1024 * 1024):
                            f.write(chunk)
                    saved_count += 1
                except Exception as e:
                    messages.warning(request, f'保存文件失败：{file.name} - {str(e)}')

            # 7. GraphRAG导入逻辑
            import_success = False
            import_error_msg = ""

            if saved_count > 0:
                try:
                    import_result = run_graphrag_import()

                    if import_result:
                        reload_success = qa_service.reload_data()
                        if reload_success:
                            import_success = True
                            import_error_msg = ""
                        else:
                            import_error_msg = "Neo4j导入成功，但QA服务刷新失败"
                    else:
                        import_error_msg = "run_graphrag_import执行返回失败"

                    # 验证lancedb目录
                    lancedb_check_path = os.path.join(artifacts_dir, 'lancedb')
                    if not os.path.exists(lancedb_check_path) and import_success:
                        messages.warning(request, "提示：lancedb目录未生成（不影响基础查询功能）")

                except Exception as import_e:
                    import_error_msg = f"导入失败：{str(import_e)}"
                    error_trace = traceback.format_exc()
                    messages.error(request, f'导入错误详情：{error_trace[:500]}')  # 限制长度

            # 8. 上传提示优化
            if saved_count == 0:
                messages.error(request, '❌ 未成功保存任何文件！')
            elif import_success:
                messages.success(
                    request,
                    f'✅ 成功上传 {saved_count} 个文件！\n'
                    f'Parquet文件路径：{artifacts_dir}\n'
                    f'✅ GraphRAG数据导入完成，可正常查询！'
                )
            else:
                messages.warning(
                    request,
                    f'✅ 成功上传 {saved_count} 个文件！\n'
                    f'Parquet文件路径：{artifacts_dir}\n'
                    f'❌ GraphRAG导入失败：{import_error_msg}\n'
                    f'⚠️ 文件已保存，可手动执行导入！'
                )

        except TooManyFilesSent:
            max_files = getattr(settings, 'DATA_UPLOAD_MAX_NUMBER_FILES', 100)
            messages.error(request, f'上传失败！文件数量超过限制（最多 {max_files} 个）')
        except OSError as e:
            messages.error(request, f'文件保存失败：{str(e)}，请检查目录权限！')
        except Exception as e:
            messages.error(request, f'上传出错：{str(e)}')
            messages.error(request, f'错误详情：{traceback.format_exc()[:500]}')

        return redirect('manager:manager_home')

    # GET请求返回上传页面
    return redirect('manager:manager_home')
