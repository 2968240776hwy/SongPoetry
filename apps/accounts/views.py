from django.contrib.auth.hashers import make_password
from .forms import RegisterForm, LoginForm
from django.contrib.auth import login  # 导入Django登录函数
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from .models import User  # 自定义User模型
import logging
from django.contrib.auth import logout as auth_logout  # 导入内置退出

logger = logging.getLogger(__name__)


# 注册视图
def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            # 用 make_password 加密密码后再存储
            encrypted_pwd = make_password(form.cleaned_data['password'])  # 密码加密
            # 创建用户时存入加密后的密码
            User.objects.create(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=encrypted_pwd,  # 存加密密码，不是明文！
                user_type=0  # 默认设为普通用户（和登录视图的 user_type=0 匹配）
            )
            return render(request, 'accounts/register.html', {'register_success': '注册成功'})
        else:
            # 错误信息收集（不变）
            errors = {}
            if form.errors.get('username'):
                errors['username_error'] = form.errors['username'][0]
            if form.errors.get('email'):
                errors['email_error'] = form.errors['email'][0]
            if form.errors.get('password'):
                errors['password_error'] = form.errors['password'][0]
            return render(request, 'accounts/register.html', errors)
    return render(request, 'accounts/register.html')


# 普通用户登录
def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            try:
                # 获取普通用户
                user = User.objects.get(username=username, user_type=0)
                # 验证加密密码
                if user.check_password(password) and user.is_active:
                    login(request, user)
                    request.session['user_type'] = user.user_type
                    return redirect('sushi_qa:qa_page')
                else:
                    return render(request, 'accounts/login.html', {'user_error': '用户名或密码错误'})
            except User.DoesNotExist:
                return render(request, 'accounts/login.html', {'user_error': '用户名或密码错误'})
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


# 退出登录
def logout(request):
    auth_logout(request)
    request.session.flush()
    # 跳转登录页：用「应用命名空间:URL名称」
    return redirect('accounts:user_login')  # 对应 accounts 应用下的 user_login 路由


def admin_login(request):
    # 已登录且是管理员 → 直接跳管理首页
    if request.user.is_authenticated and request.user.user_type == 1:
        # 获取next_url时设置默认值，避免KeyError
        next_url = request.session.get('next_url', reverse('manager:manager_home'))
        # 检查next_url是否存在再删除
        if 'next_url' in request.session:
            del request.session['next_url']
        return redirect(next_url)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not username or not password:
            messages.error(request, '用户名和密码不能为空')
            return render(request, 'accounts/login.html')

        try:
            user = User.objects.get(username=username, user_type=1)

            if not user.is_active:
                logger.warning(f"管理员账号[{username}]尝试登录，账号已禁用")
                messages.error(request, '该账号已被禁用，请联系联系超级管理员')
                return render(request, 'accounts/login.html')

            if user.check_password(password):
                login(request, user)
                user.last_login = timezone.now()
                user.save(update_fields=['last_login'])

                # 同样优化：获取next_url时设置默认值
                next_url = request.session.get('next_url', reverse('manager:manager_home'))
                # 检查存在再删除
                if 'next_url' in request.session:
                    del request.session['next_url']

                logger.info(f"管理员[{username}]登录成功")
                messages.success(request, f'欢迎回来，{username}！')
                return redirect(next_url)

            else:
                logger.warning(f"管理员[{username}]登录失败，密码错误")
                messages.error(request, '管理员账号或密码错误')
                return render(request, 'accounts/login.html')

        except User.DoesNotExist:
            logger.warning(f"不存在的管理员账号[{username}]尝试登录")
            messages.error(request, '管理员账号或密码错误')
            return render(request, 'accounts/login.html')
        except Exception as e:
            logger.error(f"管理员登录异常: {str(e)}", exc_info=True)
            messages.error(request, '登录过程出现错误，请稍后重试')
            return render(request, 'accounts/login.html')

    return render(request, 'accounts/login.html')
