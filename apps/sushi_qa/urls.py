from django.urls import path
from . import views

urlpatterns = [
    path('', views.sushi_qa, name='sushi_qa'),  # 苏轼问答页面路由
]