from django.urls import path
from . import views

urlpatterns = [
    # 可视化页面主路由
    path('', views.visualization_view, name='visualization'),

    # 数据接口路由
    path('api/author_productivity/', views.author_productivity, name='author_productivity'),
    path('api/rhythmic_popularity/', views.rhythmic_popularity, name='rhythmic_popularity'),
    path('api/emotion_analysis/', views.emotion_analysis, name='emotion_analysis'),
    path('api/word_cloud/', views.word_cloud, name='word_cloud'),
    path('api/author_work_graph/', views.author_work_graph, name='author_work_graph'),
]