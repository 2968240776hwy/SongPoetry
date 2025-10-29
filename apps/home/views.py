from django.shortcuts import render

# Create your views here.
# apps/home/views.py
from django.shortcuts import render


def index(request):
    # 可以在这里查询数据库，获取轮播的宋词数据
    poems = [
        {"title": "八六子·倚危亭", "content": "倚危亭。恨如芳草..."},
        {"title": "水调歌头·明月几时有", "content": "明月几时有..."},
    ]
    return render(request, 'home/index.html', {"poems": poems})  # 传递数据到模板