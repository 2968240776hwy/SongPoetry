from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.contrib.auth import get_user_model
from django.utils import timezone  # 导入Django时区工具
from .models import UserDialogue
from .qa_service import qa_service
import logging
import asyncio
from django.contrib.auth.mixins import LoginRequiredMixin  # 确保登录才能访问

logger = logging.getLogger(__name__)
User = get_user_model()


class QAPageView(View):
    """展示问答页面：传递用户历史会话数据"""

    def get(self, request):
        context = {}
        # 仅登录用户查询历史会话（按时间倒序，取最近10条）
        if request.user.is_authenticated:
            # 查询当前用户的历史会话，按提问时间倒序（最新的在前）
            user_dialogues = UserDialogue.objects.filter(
                user=request.user
            ).order_by("-create_time")[:10]  # 限制最多显示10条
            context["user_dialogues"] = user_dialogues
        return render(request, "sushi_qa/qa.html", context)  # 将数据传递到模板


class QAQueryView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "未登录", "need_login": True}, status=401)

        try:
            question = request.POST.get("question", "").strip()
            if not question:
                return JsonResponse({"error": "请输入问题"}, status=400)

            logger.info(f"收到用户[{request.user.username}]的查询: {question}")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                answer = loop.run_until_complete(qa_service.query(question))
            finally:
                loop.close()

            # 用timezone.now()生成带时区的时间
            UserDialogue.objects.create(
                user_id=request.user.id,
                username=request.user.username,
                question=question,
                answer=str(answer),
                create_time=timezone.now()
            )
            logger.info(f"用户[{request.user.username}]的问答记录已保存到数据库")

            return JsonResponse({"answer": str(answer)})

        except Exception as e:
            logger.error(f"查询失败: {str(e)}", exc_info=True)
            return JsonResponse({"error": "服务器处理失败"}, status=500)


# 在views.py中添加
# 查询单条对话详情的视图（需登录）
class DialogueDetailView(LoginRequiredMixin, View):
    login_url = '/accounts/login/'  # 未登录跳转登录页

    def get(self, request):
        try:
            # 1. 获取前端传递的对话ID
            dialogue_id = request.GET.get('dialogue_id')
            if not dialogue_id:
                return JsonResponse({"error": "缺少对话ID"}, status=400)

            # 2. 查询当前用户的该条对话（只能查自己的对话，防止越权）
            dialogue = UserDialogue.objects.get(
                id=dialogue_id,
                user=request.user  # 只允许查询当前登录用户的对话
            )

            # 3. 返回对话详情（问题+答案）
            return JsonResponse({
                "question": dialogue.question,
                "answer": dialogue.answer
            })

        except UserDialogue.DoesNotExist:
            # 对话不存在或不属于当前用户
            return JsonResponse({"error": "对话不存在或无权限访问"}, status=404)
        except Exception as e:
            return JsonResponse({"error": f"查询失败：{str(e)}"}, status=500)
