"""
URL configuration for SongPoetry project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path('', include('apps.home.urls')),  # 首页路由
    path('search/', include('apps.search.urls')),  # 宋词检索路由
    path('visualization/', include('apps.visualization.urls')),  # 可视化路由
    path('sushi-qa/', include('apps.sushi_qa.urls')),  # 苏轼问答路由
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)  # 开发时静态文件访问
