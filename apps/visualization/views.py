# apps/visualization/views.py
from django.shortcuts import render

def visualization_view(request):
    """可视化分析页面的视图函数，返回模板页面"""
    # 后续可在此添加可视化数据（如词频统计、流派分布等）
    context = {
        "title": "宋词可视化分析",
        "description": "通过图表直观展示宋词的艺术特色与时代特征"
    }
    return render(request, 'visualization/viz.html', context)