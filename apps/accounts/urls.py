# apps/accounts/urls.py
from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # 注册页面
    path('register/', views.register, name='register'),
    # 普通用户登录页面
    path('login/', views.user_login, name='user_login'),
    # 退出登录
    path('logout/', LogoutView.as_view(next_page='accounts:user_login'), name='logout'),
    # 管理员登录
    path('admin_login/', views.admin_login, name='admin_login'),  # 管理员登录页
]
