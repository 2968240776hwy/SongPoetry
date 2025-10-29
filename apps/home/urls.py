# apps/home/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='home'),  # 首页路由，对应 http://localhost:8000/
]