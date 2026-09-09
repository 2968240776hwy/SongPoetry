# apps/sushi_qa/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

# 获取项目的用户模型
User = get_user_model()


class UserDialogue(models.Model):
    """用户问答记录表：存储一问一答数据"""
    # 用户关联（外键，关联User表，用户删除时问答记录也删除）
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="dialogues",
        verbose_name="关联用户"
    )
    # 用户名
    username = models.CharField(max_length=16, verbose_name="用户名")
    # 问答内容
    question = models.TextField(verbose_name="用户问题")
    answer = models.TextField(verbose_name="模型回答")
    # 时间字段（自动记录创建时间）
    create_time = models.DateTimeField(default=timezone.now, verbose_name="提问时间")

    class Meta:
        db_table = "user_dialogue"  # 数据库表名
        verbose_name = "用户问答记录"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]  # 按提问时间倒序排列（最新的在前）

    def __str__(self):
        """后台显示时，用“用户名-问题前20字”标识记录"""
        return f"{self.username}: {self.question[:20]}..."
