from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from .neo4j_utils import run_neo4j_query, check_graph_structure, test_neo4j_connection
import json
import logging

logger = logging.getLogger(__name__)


def search_view(request):
    conn_status, conn_msg = test_neo4j_connection()
    struct_status, struct_msg = check_graph_structure() if conn_status else (False, "未校验图谱")

    return render(
        request,
        'search/search.html',
        {
            'neo4j_connected': conn_status,
            'neo4j_msg': conn_msg,
            'graph_struct_msg': struct_msg
        }
    )


def search_results(request):
    if request.method != 'POST':
        return HttpResponseRedirect(reverse('search'))

    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"error": "请求格式错误，需提交 JSON 数据"},
                status=400
            )
    else:
        data = request.POST.dict()

    query = data.get("query", "").strip()
    search_type = data.get("type", "").strip()
    page = int(data.get("page", 1))
    page_size = min(int(data.get("page_size", 10)), 10)
    skip = (page - 1) * page_size

    if not query:
        return JsonResponse(
            {"error": "检索关键词不能为空"},
            status=400
        )

    # 初始化查询语句和参数
    cypher = ""
    count_cypher = ""
    params = {"query": query, "skip": skip, "page_size": page_size}

    # 1. 人物检索
    if search_type == "person":
        # 计数查询（同时匹配name和description）
        count_cypher = """
            MATCH (e:__Entity__:人物)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            RETURN COUNT(e) AS total
        """
        # 数据查询（精确匹配优先，再按名称升序）
        cypher = """
            MATCH (e:__Entity__:人物)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            OPTIONAL MATCH (e)-[rel:RELATED]->(related_e:__Entity__)
            WITH e,
                 COLLECT(DISTINCT {
                     entity: {
                         id: related_e.id,
                         name: related_e.name,
                         description: related_e.description,
                         entity_type: CASE 
                             WHEN [label IN labels(related_e) WHERE label <> '__Entity__'] = [] THEN '未知类型'
                             ELSE [label IN labels(related_e) WHERE label <> '__Entity__'][0]
                         END
                     },
                     relationship: rel {.description, .weight}
                 })[0..10] AS related_entities,
                 // 精确匹配标记：名称完全一致的优先级最高
                 CASE WHEN e.name = $query THEN 1 ELSE 0 END AS is_exact_match
            RETURN {
                entity: {
                    id: e.id,
                    name: e.name,
                    description: e.description,
                    fields: e.fields
                },
                entity_type: '人物',
                related_entities: related_entities
            } AS result
            // 排序规则：精确匹配优先 > 名称升序
            ORDER BY is_exact_match DESC, e.name ASC
            SKIP $skip LIMIT $page_size
        """

    # 2. 作品检索
    elif search_type == "work":
        # 计数查询
        count_cypher = """
            MATCH (e:__Entity__:作品)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            RETURN COUNT(e) AS total
        """
        # 数据查询（精确匹配优先）
        cypher = """
            MATCH (e:__Entity__:作品)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            OPTIONAL MATCH (e)-[rel:RELATED]->(related_e:__Entity__)
            WITH e,
                 COLLECT(DISTINCT {
                     entity: {
                         id: related_e.id,
                         name: related_e.name,
                         description: related_e.description,
                         entity_type: CASE 
                             WHEN [label IN labels(related_e) WHERE label <> '__Entity__'] = [] THEN '未知类型'
                             ELSE [label IN labels(related_e) WHERE label <> '__Entity__'][0]
                         END
                     },
                     relationship: rel {.description, .weight}
                 })[0..10] AS related_entities,
                 // 精确匹配标记
                 CASE WHEN e.name = $query THEN 1 ELSE 0 END AS is_exact_match
            RETURN {
                entity: {
                    id: e.id,
                    name: e.name,
                    description: e.description,
                    fields: e.fields
                },
                entity_type: '作品',
                related_entities: related_entities
            } AS result
            // 排序规则：精确匹配优先 > 名称升序
            ORDER BY is_exact_match DESC, e.name ASC
            SKIP $skip LIMIT $page_size
        """

    # 3. 意象检索
    elif search_type == "image":
        # 计数查询
        count_cypher = """
            MATCH (e:__Entity__:意象)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            RETURN COUNT(e) AS total
        """
        # 数据查询（精确匹配优先）
        cypher = """
            MATCH (e:__Entity__:意象)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            OPTIONAL MATCH (e)-[rel:RELATED]->(related_e:__Entity__)
            WITH e,
                 COLLECT(DISTINCT {
                     entity: {
                         id: related_e.id,
                         name: related_e.name,
                         description: related_e.description,
                         entity_type: CASE 
                             WHEN [label IN labels(related_e) WHERE label <> '__Entity__'] = [] THEN '未知类型'
                             ELSE [label IN labels(related_e) WHERE label <> '__Entity__'][0]
                         END
                     },
                     relationship: rel {.description, .weight}
                 })[0..10] AS related_entities,
                 // 精确匹配标记
                 CASE WHEN e.name = $query THEN 1 ELSE 0 END AS is_exact_match
            RETURN {
                entity: {
                    id: e.id,
                    name: e.name,
                    description: e.description,
                    fields: e.fields
                },
                entity_type: '意象',
                related_entities: related_entities
            } AS result
            // 排序规则：精确匹配优先 > 名称升序
            ORDER BY is_exact_match DESC, e.name ASC
            SKIP $skip LIMIT $page_size
        """

    # 4. 时间检索
    elif search_type == "time":
        # 计数查询
        count_cypher = """
            MATCH (e:__Entity__:时间)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            RETURN COUNT(e) AS total
        """
        # 数据查询（精确匹配优先）
        cypher = """
            MATCH (e:__Entity__:时间)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            OPTIONAL MATCH (e)-[rel:RELATED]->(related_e:__Entity__)
            WITH e,
                 COLLECT(DISTINCT {
                     entity: {
                         id: related_e.id,
                         name: related_e.name,
                         description: related_e.description,
                         entity_type: CASE 
                             WHEN [label IN labels(related_e) WHERE label <> '__Entity__'] = [] THEN '未知类型'
                             ELSE [label IN labels(related_e) WHERE label <> '__Entity__'][0]
                         END
                     },
                     relationship: rel {.description, .weight}
                 })[0..10] AS related_entities,
                 // 精确匹配标记
                 CASE WHEN e.name = $query THEN 1 ELSE 0 END AS is_exact_match
            RETURN {
                entity: {
                    id: e.id,
                    name: e.name,
                    description: e.description,
                    fields: e.fields
                },
                entity_type: '时间',
                related_entities: related_entities
            } AS result
            // 排序规则：精确匹配优先 > 名称升序
            ORDER BY is_exact_match DESC, e.name ASC
            SKIP $skip LIMIT $page_size
        """

    # 5. 地点检索
    elif search_type == "location":
        # 计数查询
        count_cypher = """
            MATCH (e:__Entity__:地点)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            RETURN COUNT(e) AS total
        """
        # 数据查询（精确匹配优先）
        cypher = """
            MATCH (e:__Entity__:地点)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            OPTIONAL MATCH (e)-[rel:RELATED]->(related_e:__Entity__)
            WITH e,
                 COLLECT(DISTINCT {
                     entity: {
                         id: related_e.id,
                         name: related_e.name,
                         description: related_e.description,
                         entity_type: CASE 
                             WHEN [label IN labels(related_e) WHERE label <> '__Entity__'] = [] THEN '未知类型'
                             ELSE [label IN labels(related_e) WHERE label <> '__Entity__'][0]
                         END
                     },
                     relationship: rel {.description, .weight}
                 })[0..10] AS related_entities,
                 // 精确匹配标记
                 CASE WHEN e.name = $query THEN 1 ELSE 0 END AS is_exact_match
            RETURN {
                entity: {
                    id: e.id,
                    name: e.name,
                    description: e.description,
                    fields: e.fields
                },
                entity_type: '地点',
                related_entities: related_entities
            } AS result
            // 排序规则：精确匹配优先 > 名称升序
            ORDER BY is_exact_match DESC, e.name ASC
            SKIP $skip LIMIT $page_size
        """

    # 6. 事件检索
    elif search_type == "event":
        # 计数查询
        count_cypher = """
            MATCH (e:__Entity__:事件)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            RETURN COUNT(e) AS total
        """
        # 数据查询（精确匹配优先）
        cypher = """
            MATCH (e:__Entity__:事件)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            OPTIONAL MATCH (e)-[rel:RELATED]->(related_e:__Entity__)
            WITH e,
                 COLLECT(DISTINCT {
                     entity: {
                         id: related_e.id,
                         name: related_e.name,
                         description: related_e.description,
                         entity_type: CASE 
                             WHEN [label IN labels(related_e) WHERE label <> '__Entity__'] = [] THEN '未知类型'
                             ELSE [label IN labels(related_e) WHERE label <> '__Entity__'][0]
                         END
                     },
                     relationship: rel {.description, .weight}
                 })[0..10] AS related_entities,
                 // 精确匹配标记
                 CASE WHEN e.name = $query THEN 1 ELSE 0 END AS is_exact_match
            RETURN {
                entity: {
                    id: e.id,
                    name: e.name,
                    description: e.description,
                    fields: e.fields
                },
                entity_type: '事件',
                related_entities: related_entities
            } AS result
            // 排序规则：精确匹配优先 > 名称升序
            ORDER BY is_exact_match DESC, e.name ASC
            SKIP $skip LIMIT $page_size
        """

    # 7. 典故检索
    elif search_type == "allusion":
        # 计数查询
        count_cypher = """
            MATCH (e:__Entity__:典故)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            RETURN COUNT(e) AS total
        """
        # 数据查询（精确匹配优先）
        cypher = """
            MATCH (e:__Entity__:典故)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            OPTIONAL MATCH (e)-[rel:RELATED]->(related_e:__Entity__)
            WITH e,
                 COLLECT(DISTINCT {
                     entity: {
                         id: related_e.id,
                         name: related_e.name,
                         description: related_e.description,
                         entity_type: CASE 
                             WHEN [label IN labels(related_e) WHERE label <> '__Entity__'] = [] THEN '未知类型'
                             ELSE [label IN labels(related_e) WHERE label <> '__Entity__'][0]
                         END
                     },
                     relationship: rel {.description, .weight}
                 })[0..10] AS related_entities,
                 // 精确匹配标记
                 CASE WHEN e.name = $query THEN 1 ELSE 0 END AS is_exact_match
            RETURN {
                entity: {
                    id: e.id,
                    name: e.name,
                    description: e.description,
                    fields: e.fields
                },
                entity_type: '典故',
                related_entities: related_entities
            } AS result
            // 排序规则：精确匹配优先 > 名称升序
            ORDER BY is_exact_match DESC, e.name ASC
            SKIP $skip LIMIT $page_size
        """

    # 8. 情感检索
    elif search_type == "emotion":
        # 计数查询
        count_cypher = """
            MATCH (e:__Entity__:情感)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            RETURN COUNT(e) AS total
        """
        # 数据查询（精确匹配优先）
        cypher = """
            MATCH (e:__Entity__:情感)
            WHERE e.name CONTAINS $query OR e.description CONTAINS $query
            OPTIONAL MATCH (e)-[rel:RELATED]->(related_e:__Entity__)
            WITH e,
                 COLLECT(DISTINCT {
                     entity: {
                         id: related_e.id,
                         name: related_e.name,
                         description: related_e.description,
                         entity_type: CASE 
                             WHEN [label IN labels(related_e) WHERE label <> '__Entity__'] = [] THEN '未知类型'
                             ELSE [label IN labels(related_e) WHERE label <> '__Entity__'][0]
                         END
                     },
                     relationship: rel {.description, .weight}
                 })[0..10] AS related_entities,
                 // 精确匹配标记
                 CASE WHEN e.name = $query THEN 1 ELSE 0 END AS is_exact_match
            RETURN {
                entity: {
                    id: e.id,
                    name: e.name,
                    description: e.description,
                    fields: e.fields
                },
                entity_type: '情感',
                related_entities: related_entities
            } AS result
            // 排序规则：精确匹配优先 > 名称升序
            ORDER BY is_exact_match DESC, e.name ASC
            SKIP $skip LIMIT $page_size
        """

    else:
        return JsonResponse(
            {"error": "不支持的检索类型，请选择：person/work/image/time/location/event/allusion/emotion"},
            status=400
        )

    try:
        logger.info(f"执行检索：类型={search_type}，关键词={query}，页大小={page_size}")

        # 先查询总数
        count_results = run_neo4j_query(count_cypher, {"query": query})
        total_count = count_results[0]['total'] if count_results else 0

        # 再查询分页数据
        results = run_neo4j_query(cypher, params)

        if not results:
            logger.info(f"未找到匹配结果：类型={search_type}，关键词={query}")
            return JsonResponse({
                "success": True,
                "count": total_count,  # 返回总条数
                "results": [],
                "query": query,
                "type": search_type
            }, status=200)

        # 解析fields JSON字符串
        formatted_results = []
        for record in results:
            result = record.get('result', {})
            entity = result.get('entity', {})
            fields_str = entity.get('fields', '{}')

            # 解析JSON字符串为字典
            try:
                fields = json.loads(fields_str)
            except json.JSONDecodeError:
                fields = {}
                logger.warning(f"解析fields失败：{fields_str}")

            # 根据实体类型提取对应属性
            if result.get('entity_type') == '人物':
                entity.update({
                    'person_gender': fields.get('person_gender'),
                    'person_birth': fields.get('person_birth'),
                    'person_dead': fields.get('person_dead'),
                    'person_nativeplace': fields.get('person_nativeplace'),
                    'person_deathplace': fields.get('person_deathplace'),
                    'person_character': fields.get('person_character'),
                    'person_nickname': fields.get('person_nickname')
                })
            elif result.get('entity_type') == '作品':
                entity.update({
                    'work_content': fields.get('work_content'),
                    'work_brand': fields.get('work_brand'),
                    'work_time': fields.get('work_time')
                })
            elif result.get('entity_type') == '意象':
                entity.update({
                    'yixiang_means': fields.get('yixiang_means')
                })
            elif result.get('entity_type') == '时间':
                entity.update({
                    'date_era': fields.get('date_era')
                })
            elif result.get('entity_type') == '地点':
                entity.update({
                    'place_ancientname': fields.get('place_ancientname'),
                    'place_nowname': fields.get('place_nowname')
                })
            elif result.get('entity_type') == '事件':
                entity.update({
                    'event_time': fields.get('event_time'),
                    'event_place': fields.get('event_place')
                })
            elif result.get('entity_type') == '典故':
                entity.update({
                    'diangu_source': fields.get('diangu_source')
                })
            elif result.get('entity_type') == '情感':
                entity.update({
                    'emotion_strength': fields.get('emotion_strength')
                })

            # 移除原始fields字符串
            entity.pop('fields', None)
            formatted_results.append(result)

        logger.info(f"检索成功：共{total_count}条，返回{len(formatted_results)}条结果")

        return JsonResponse({
            "success": True,
            "count": total_count,  # 返回总匹配数
            "results": formatted_results,
            "query": query,
            "type": search_type
        }, status=200)

    except Exception as e:
        logger.error(f"检索失败：{str(e)}", exc_info=True)
        if "MemoryPoolOutOfMemoryError" in str(e):
            return JsonResponse({
                "error": "检索失败：数据量过大，超出Neo4j内存限制",
                "detail": "1. 请使用更精确的关键词；2. 分多次检索；3. 联系管理员增大内存配置"
            }, status=500)
        elif "SyntaxError" in str(e):
            return JsonResponse({
                "error": "Cypher语法错误",
                "detail": f"查询语句存在错误：{str(e)}"
            }, status=500)
        return JsonResponse({
            "error": f"检索失败：{str(e)}",
            "detail": "请检查Neo4j连接或图谱结构"
        }, status=500)