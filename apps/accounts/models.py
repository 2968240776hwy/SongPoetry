# models.py
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager


# 1. 自定义用户管理器
class UserManager(BaseUserManager):
    # 创建普通用户
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError('必须提供邮箱')
        if not username:
            raise ValueError('必须提供用户名')

        # 标准化邮箱（小写域名部分）
        email = self.normalize_email(email)
        # 创建用户对象
        user = self.model(username=username, email=email, **extra_fields)
        # 加密密码
        user.set_password(password)
        user.save(using=self._db)
        return user

    # 创建管理员用户（用于后台管理）
    def create_superuser(self, username, email, password=None, **extra_fields):
        # 强制设置管理员权限
        extra_fields.setdefault('user_type', 1)  # 1 是你的管理员类型
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', True)  # 允许登录 Django 后台
        extra_fields.setdefault('is_superuser', True)  # 超级管理员权限

        return self.create_user(username, email, password, **extra_fields)


# 2. 自定义 User 模型
class User(AbstractBaseUser, PermissionsMixin):
    USER_TYPE_CHOICES = (
        (0, '普通用户'),
        (1, '管理员'),
    )

    # 基础字段
    username = models.CharField(max_length=16, unique=True, verbose_name='用户名')
    email = models.EmailField(unique=True, verbose_name='邮箱')
    user_type = models.SmallIntegerField(choices=USER_TYPE_CHOICES, default=0, verbose_name='用户类型')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    # Django 后台管理必需字段
    is_staff = models.BooleanField(default=False, verbose_name='是否允许登录后台')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    # 3. 认证系统必需配置
    objects = UserManager()  # 绑定自定义管理器
    USERNAME_FIELD = 'username'  # 登录时使用的字段（这里用用户名，也可以用邮箱）
    REQUIRED_FIELDS = ['email']  # 创建用户时必需的额外字段（除了 USERNAME_FIELD）

    class Meta:
        db_table = 'user'
        verbose_name = '用户'
        verbose_name_plural = verbose_name

    # 4. 可选：优化用户对象的字符串显示
    def __str__(self):
        return self.username
