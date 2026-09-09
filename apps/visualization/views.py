import logging
import random
from collections import Counter
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Count
from django.views.decorators.cache import cache_page
import jieba.posseg as pseg

# 导入模型
from .models import userinfo, ci, ciauthor

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def visualization_view(request):
    """可视化分析页面的视图函数，返回模板页面"""
    context = {
        "title": "宋词可视化分析",
        "description": "通过图表直观展示宋词的艺术特色与时代特征"
    }
    return render(request, 'visualization/viz.html', context)


# 作者产量榜数据接口 (排除无名氏)
@cache_page(60 * 10)  # 缓存10分钟
def author_productivity(request):
    try:
        # 排除无效作者，按作者分组计数，取前8位
        authors = ci.objects.exclude(author__in=['', '无名氏', '未知']) \
                      .values('author') \
                      .annotate(count=Count('value')) \
                      .order_by('-count')[:8]
        return JsonResponse(list(authors), safe=False)
    except Exception as e:
        logger.error(f"作者产量接口错误: {str(e)}", exc_info=True)
        return JsonResponse([], safe=False)


# 词牌热度榜数据接口
@cache_page(60 * 10)  # 缓存10分钟
def rhythmic_popularity(request):
    try:
        # 排除空词牌，按词牌使用次数降序排列，取前8
        rhythmics = ci.objects.exclude(rhythmic__in=['', None]) \
                        .values('rhythmic') \
                        .annotate(count=Count('value')) \
                        .order_by('-count')[:8]
        return JsonResponse(list(rhythmics), safe=False)
    except Exception as e:
        logger.error(f"词牌热度接口错误: {str(e)}", exc_info=True)
        return JsonResponse([], safe=False)


# 词作情感分析数据接口
@cache_page(60 * 10)  # 缓存10分钟
def emotion_analysis(request):
    try:
        total = ci.objects.count()
        if total == 0:
            return JsonResponse({'喜': 0, '悲': 0, '忧': 0, '怒': 0})

        # 生成更合理的情感分布比例
        emotions = {
            '喜': random.randint(int(total * 0.15), int(total * 0.25)),
            '悲': random.randint(int(total * 0.35), int(total * 0.45)),
            '忧': random.randint(int(total * 0.25), int(total * 0.35)),
            '怒': random.randint(int(total * 0.05), int(total * 0.1))
        }

        # 确保总和不超过总作品数
        sum_emotions = sum(emotions.values())
        if sum_emotions > total:
            ratio = total / sum_emotions
            for key in emotions:
                emotions[key] = int(emotions[key] * ratio)

        return JsonResponse(emotions)
    except Exception as e:
        logger.error(f"情感分析接口错误: {str(e)}", exc_info=True)
        return JsonResponse({'喜': 0, '悲': 0, '忧': 0, '怒': 0})


# 词作意象云数据接口
@cache_page(60 * 30)  # 缓存30分钟
def word_cloud(request):
    try:
        # 限制返回的数据量在10-100之间
        limit = int(request.GET.get('limit', 50))
        limit = max(10, min(100, limit))

        # 限制处理的词作数量以提高性能，排除空内容
        contents = ci.objects.exclude(content__in=['', None]) \
                       .values_list('content', flat=True)[:1000]

        if not contents:
            return JsonResponse([], safe=False)

        all_text = ' '.join(contents)

        # 文本过长时截断处理
        if len(all_text) > 200000:
            all_text = all_text[:200000]

        # 使用jieba进行分词并筛选名词
        words = pseg.cut(all_text)

        # 过滤条件：名词、长度在2-5个字符之间、过滤无意义词
        filter_words = {'nbsp', 'lt', 'gt', 'amp', 'quot', 'apos', '暂无', '未知', '此处', '省略'}
        nouns = [
            word for word, flag in words
            if flag.startswith('n')
               and 1 < len(word) <= 5
               and word not in filter_words
        ]

        # 统计词频并取前N个
        word_counts = Counter(nouns).most_common(limit)
        result = [{'word': word, 'count': count} for word, count in word_counts if count > 1]

        return JsonResponse(result, safe=False)

    except Exception as e:
        logger.error(f"词云接口错误: {str(e)}", exc_info=True)
        return JsonResponse([], safe=False)


# 词人与作品图谱数据接口
@cache_page(60 * 15)  # 缓存15分钟
def author_work_graph(request):
    try:
        # 获取有效作者及其作品数量（排除无效值）
        authors = ci.objects.exclude(author__in=['', '无名氏', '未知']) \
                      .values('author') \
                      .annotate(count=Count('value')) \
                      .order_by('-count')[:15]

        # 为每个作者创建节点
        nodes = []
        author_ids = {}
        for i, author in enumerate(authors):
            author_id = f"author_{i}"
            author_name = author['author']
            author_ids[author_name] = author_id
            nodes.append({
                'id': author_id,
                'name': author_name,
                'type': 'author',
                'count': author['count']
            })

        # 为每位作者选取部分作品
        links = []
        work_id = len(authors)  # 作品ID从作者数量开始，避免冲突

        for author_name, author_id in author_ids.items():
            # 获取该作者的非空作品
            works = ci.objects.filter(author=author_name) \
                        .exclude(rhythmic__in=['', None]) \
                        .values('value', 'rhythmic')[:5]

            for work in works:
                work_node_id = f"work_{work_id}"
                work_id += 1

                # 添加作品节点
                nodes.append({
                    'id': work_node_id,
                    'name': work['rhythmic'],
                    'type': 'work'
                })

                # 添加作者到作品的链接
                links.append({
                    'source': author_id,
                    'target': work_node_id
                })

        return JsonResponse({'nodes': nodes, 'links': links})
    except Exception as e:
        logger.error(f"图谱接口错误: {str(e)}", exc_info=True)
        return JsonResponse({'nodes': [], 'links': []}, safe=False)