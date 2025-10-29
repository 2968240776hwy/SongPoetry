# apps/search/urls.py
from django.urls import path
from . import views  # 必须导入当前app的views

urlpatterns = [
    # 路径为空（对应/search/），视图函数为search_view，名称必须是'search'
    path('', views.search_view, name='search'),
]