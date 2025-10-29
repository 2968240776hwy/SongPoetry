from django.shortcuts import render


def sushi_qa(request):
    # 目前仅返回页面，后续可添加上下文数据
    return render(request, 'sushi_qa/qa.html')