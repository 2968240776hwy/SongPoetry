# 知识检索服务
from neo4j import GraphDatabase, exceptions
from django.conf import settings  # 导入 Django 配置


def get_neo4j_driver():
    """初始化 Neo4j 驱动（从 Django settings 读取配置）"""
    try:
        # 从 settings 读取 Neo4j 配置
        neo4j_conf = settings.NEO4J_CONFIG['default']
        uri = neo4j_conf['URI']

        # 自动补全端口
        uri = uri if ":" in uri else f"{uri}:7687"

        driver = GraphDatabase.driver(uri, auth=(neo4j_conf['USERNAME'], neo4j_conf['PASSWORD']))
        driver.verify_connectivity()
        return driver
    except exceptions.AuthError:
        # 从配置中读取密码用于提示
        neo4j_conf = settings.NEO4J_CONFIG['default']
        raise Exception(f"Neo4j 用户名/密码错误（当前密码：{neo4j_conf['PASSWORD']}）")
    except exceptions.ServiceUnavailable:
        neo4j_conf = settings.NEO4J_CONFIG['default']
        uri = neo4j_conf['URI'] if ":" in neo4j_conf['URI'] else f"{neo4j_conf['URI']}:7687"
        raise Exception(f"Neo4j 服务未启动（URI：{uri}）")
    except Exception as e:
        raise Exception(f"驱动初始化失败：{str(e)}")


def test_neo4j_connection():
    """测试 Neo4j 连接"""
    driver = get_neo4j_driver()
    try:
        # 从 settings 读取数据库名
        neo4j_conf = settings.NEO4J_CONFIG['default']
        with driver.session(database=neo4j_conf['DATABASE']):
            return True, "Neo4j 连接正常"
    except Exception as e:
        return False, f"Neo4j 连接失败：{str(e)}"
    finally:
        driver.close()


def check_graph_structure():
    """校验图谱结构"""
    driver = get_neo4j_driver()
    try:
        # 从 settings 读取数据库名
        neo4j_conf = settings.NEO4J_CONFIG['default']
        with driver.session(database=neo4j_conf['DATABASE']) as session:
            # 检查核心节点是否存在
            core_nodes = ["__Document__", "__Chunk__", "__Entity__", "__Community__"]
            missing_nodes = []
            for label in core_nodes:
                cnt = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()["c"]
                if cnt == 0:
                    missing_nodes.append(label)
            if missing_nodes:
                return False, f"图谱缺少核心节点：{','.join(missing_nodes)}（请先导入数据）"
        return True, "图谱结构符合 GraphRAG 规范"
    except Exception as e:
        return False, f"图谱校验失败：{str(e)}"
    finally:
        driver.close()


def run_neo4j_query(cypher, params=None):
    """执行 Cypher 查询并序列化结果"""
    if not cypher.strip():
        raise ValueError("Cypher 查询不能为空")

    params = params or {}
    driver = get_neo4j_driver()

    try:
        # 从 settings 读取数据库名
        neo4j_conf = settings.NEO4J_CONFIG['default']
        with driver.session(database=neo4j_conf['DATABASE']) as session:
            result = session.run(cypher, params)

            # 序列化 Neo4j 节点/关系为字典
            def serialize(value):
                if hasattr(value, "id") and hasattr(value, "labels"):
                    # 序列化节点
                    return {
                        "id": value.id,
                        "labels": list(value.labels),
                        "properties": dict(value)
                    }
                elif hasattr(value, "type") and hasattr(value, "start_node"):
                    # 序列化关系
                    return {
                        "type": value.type,
                        "start_node_id": value.start_node.id,
                        "end_node_id": value.end_node.id,
                        "properties": dict(value)
                    }
                return value

            return [{"_".join(k.split("__")): serialize(v) for k, v in record.items()}
                    for record in result.data()]
    except exceptions.Neo4jError as e:
        raise Exception(f"Cypher 语法错误：{str(e)}")
    except Exception as e:
        raise Exception(f"查询执行失败：{str(e)}")
    finally:
        driver.close()