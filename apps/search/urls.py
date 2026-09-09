# apps/search/urls.py
from django.urls import path
from . import views as yuanyou_views  # 必须导入当前app的views

urlpatterns = [
    # 路径为空
    path('', yuanyou_views.search_view, name='search'),

    # 2. 检索结果接口
    path('results/', yuanyou_views.search_results, name='search_results'),
]