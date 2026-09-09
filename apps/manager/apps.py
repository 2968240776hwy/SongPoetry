from django.apps import AppConfig
import os

class ManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.manager"

    def ready(self):
        # 检查artifacts目录是否存在，避免启动时无数据报错
        from django.conf import settings
        artifacts_path = os.path.join(settings.MEDIA_ROOT, "output", "artifacts")
        if os.path.exists(artifacts_path) and len(os.listdir(artifacts_path)) > 0:
            try:
                from .graphrag_import import run_graphrag_import
                run_graphrag_import()
                print("GraphRAG data imported successfully on app startup.")
            except Exception as e:
                print(f"Failed to import GraphRAG data on startup: {e}")