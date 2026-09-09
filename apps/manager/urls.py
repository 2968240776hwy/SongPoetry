# manage/urls.py（或 apps/manage/urls.py，根据实际路径调整）
from django.urls import path
from . import views

app_name = 'manager'

urlpatterns = [
    # 管理员首页，路径为空表示访问 /manage/ 时直接进入
    path('', views.manage_home, name='manager_home'),  # 关键：定义name用于反向解析

    # 用户管理
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:pk>/', views.user_detail, name='user_detail'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),

    # 词作管理
    path('poems/', views.poem_list, name='poem_list'),
    path('poems/create/', views.poem_create, name='poem_create'),
    path('poems/<int:pk>/', views.poem_detail, name='poem_detail'),
    path('poems/<int:pk>/edit/', views.poem_edit, name='poem_edit'),
    path('poems/<int:pk>/delete/', views.poem_delete, name='poem_delete'),

    # 词人管理
    path('authors/', views.author_list, name='author_list'),
    path('authors/create/', views.author_create, name='author_create'),
    path('authors/<int:pk>/', views.author_detail, name='author_detail'),
    path('authors/<int:pk>/edit/', views.author_edit, name='author_edit'),
    path('authors/<int:pk>/delete/', views.author_delete, name='author_delete'),

    # 对话管理
    path('dialogues/', views.dialogue_list, name='dialogue_list'),
    path('dialogues/create/', views.dialogue_create, name='dialogue_create'),
    path('dialogues/<int:pk>/', views.dialogue_detail, name='dialogue_detail'),
    path('dialogues/<int:pk>/edit/', views.dialogue_edit, name='dialogue_edit'),
    path('dialogues/<int:pk>/delete/', views.dialogue_delete, name='dialogue_delete'),

    path('folder-upload/', views.folder_upload, name='folder_upload'),
]