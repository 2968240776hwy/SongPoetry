# apps/search/views.py
from django.shortcuts import render


def search_view(request):
    # 暂时返回空页面，后续可添加检索逻辑
    return render(request, 'search/search.html')