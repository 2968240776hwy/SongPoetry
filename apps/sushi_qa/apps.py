# apps/sushi_qa/apps.py
from django.apps import AppConfig
import threading


class SushiQaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sushi_qa"

    def ready(self):
        """启动时异步初始化服务，避免阻塞"""
        def init_service():
            from .qa_service import qa_service  # 触发初始化
        threading.Thread(target=init_service).start()