import pandas as pd
from neo4j import GraphDatabase
import time
import os
from django.conf import settings

# 全局变量
driver = None


def read_parquet_safe(file_path, columns=None):
    """安全读取parquet文件，文件不存在时返回空DataFrame"""
    # 兼容 Pathlib 对象和字符串路径
    file_path = str(file_path) if hasattr(file_path, 'as_posix') else file_path
    if not os.path.exists(file_path):
        return pd.DataFrame()
    try:
        return pd.read_parquet(file_path, columns=columns)
    except Exception:
        return pd.DataFrame()


def init_neo4j_driver():
    """初始化Neo4j驱动（从Django settings读取配置）"""
    global driver
    if driver is None:
        neo4j_conf = settings.NEO4J_CONFIG['default']
        driver = GraphDatabase.driver(
            neo4j_conf['URI'],
            auth=(neo4j_conf['USERNAME'], neo4j_conf['PASSWORD'])
        )


def clear_neo4j():
    """清空Neo4j数据库"""
    init_neo4j_driver()
    neo4j_conf = settings.NEO4J_CONFIG['default']
    with driver.session(database=neo4j_conf['DATABASE']) as session:
        session.run("MATCH (n) DETACH DELETE n")


def batched_import(statement, df):
    """批量导入DataFrame到Neo4j"""
    if df.empty:
        return 0

    init_neo4j_driver()
    neo4j_conf = settings.NEO4J_CONFIG['default']
    total = len(df)
    batch_size = neo4j_conf['BATCH_SIZE']
    start_s = time.time()

    for start in range(0, total, batch_size):
        batch = df.iloc[start: min(start + batch_size, total)]
        driver.execute_query(
            "UNWIND $rows AS value " + statement,
            rows=batch.to_dict('records'),
            database_=neo4j_conf['DATABASE']
        )
    return total


def run_graphrag_import():
    """执行完整的GraphRAG导入流程"""
    # 从settings读取配置（Pathlib对象）
    graphrag_folder = settings.GRAPHRAG_FOLDER
    neo4j_conf = settings.NEO4J_CONFIG['default']

    # 检查目录是否存在（适配Pathlib）
    if not graphrag_folder.exists():
        return False

    # 初始化驱动并清空数据库
    init_neo4j_driver()
    clear_neo4j()

    # 创建约束
    for constraint in neo4j_conf['CONSTRAINTS']:
        if constraint.strip():
            driver.execute_query(constraint, database_=neo4j_conf['DATABASE'])

    # 1. 导入文档
    doc_df = read_parquet_safe(graphrag_folder / "create_final_documents.parquet", columns=["id", "title"])
    if not doc_df.empty:
        statement = """
        MERGE (d:__Document__ {id:value.id})
        SET d += value {.title}
        """
        batched_import(statement, doc_df)

    # 2. 导入文本块
    text_df = read_parquet_safe(
        graphrag_folder / "create_final_text_units.parquet",
        columns=["id", "text", "n_tokens", "document_ids"]
    )
    if not text_df.empty:
        statement = """
        MERGE (c:__Chunk__ {id:value.id})
        SET c += value {.text, .n_tokens}
        WITH c, value
        UNWIND value.document_ids AS document
        MATCH (d:__Document__ {id:document})
        MERGE (c)-[:PART_OF]->(d)
        """
        batched_import(statement, text_df)

    # 3. 导入实体
    entity_df = read_parquet_safe(
        graphrag_folder / "create_final_entities.parquet",
        columns=["name", "type", "description", "human_readable_id", "id", "description_embedding", "text_unit_ids",
                 "fields"]
    )
    if not entity_df.empty:
        entity_statement = """
        MERGE (e:__Entity__ {id: value.id})
        SET e += value {.human_readable_id, .description, name: replace(value.name, '"', ''), .fields}
        WITH e, value
        CALL db.create.setNodeVectorProperty(e, "description_embedding", value.description_embedding)
        CALL apoc.create.addLabels(e, 
            CASE 
                WHEN coalesce(value.type, "") = "" THEN [] 
                ELSE [apoc.text.upperCamelCase(replace(value.type, '"', ''))] 
            END
        ) YIELD node
        UNWIND value.text_unit_ids AS text_unit
        MATCH (c:__Chunk__ {id: text_unit})
        MERGE (c)-[:HAS_ENTITY]->(e)
        """
        batched_import(entity_statement, entity_df)

    # 4. 导入关系
    rel_df = read_parquet_safe(
        graphrag_folder / "create_final_relationships.parquet",
        columns=["source", "target", "id", "rank", "weight", "human_readable_id", "description", "text_unit_ids"]
    )
    if not rel_df.empty:
        rel_statement = """
            MATCH (source:__Entity__ {name:replace(value.source,'"','')})
            MATCH (target:__Entity__ {name:replace(value.target,'"','')})
            MERGE (source)-[rel:RELATED {id: value.id}]->(target)
            SET rel += value {.rank, .weight, .human_readable_id, .description, .text_unit_ids}
            RETURN count(*) as createdRels
        """
        batched_import(rel_statement, rel_df)

    # 5. 导入社区
    community_df = read_parquet_safe(
        graphrag_folder / "create_final_communities.parquet",
        columns=["id", "level", "title", "text_unit_ids", "relationship_ids"]
    )
    if not community_df.empty:
        statement = """
        MERGE (c:__Community__ {community:value.id})
        SET c += value {.level, .title}
        WITH *
        UNWIND value.relationship_ids as rel_id
        MATCH (start:__Entity__)-[:RELATED {id:rel_id}]->(end:__Entity__)
        MERGE (start)-[:IN_COMMUNITY]->(c)
        MERGE (end)-[:IN_COMMUNITY]->(c)
        RETURN count(distinct c) as createdCommunities
        """
        batched_import(statement, community_df)

    # 6. 导入社区报告
    community_report_df = read_parquet_safe(
        graphrag_folder / "create_final_community_reports.parquet",
        columns=["id", "community", "level", "title", "summary", "findings", "rank", "rank_explanation", "full_content"]
    )
    if not community_report_df.empty:
        community_statement = """
        MERGE (c:__Community__ {community:value.community})
        SET c += value {.level, .title, .rank, .rank_explanation, .full_content, .summary}
        WITH c, value
        UNWIND range(0, size(value.findings)-1) AS finding_idx
        WITH c, value, finding_idx, value.findings[finding_idx] as finding
        MERGE (c)-[:HAS_FINDING]->(f:Finding {id:finding_idx})
        SET f += finding
        """
        batched_import(community_statement, community_report_df)

    # 关闭驱动
    if driver is not None:
        driver.close()
    return True