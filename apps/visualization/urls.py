# apps/visualization/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # 定义路由规则：路径为空（对应/visualization/），视图函数为visualization_view，名称为'visualization'
    path('', views.visualization_view, name='visualization'),
]