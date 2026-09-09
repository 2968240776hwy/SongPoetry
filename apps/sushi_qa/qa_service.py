import pandas as pd
import tiktoken
import logging
from django.conf import settings
from graphrag.query.context_builder.entity_extraction import EntityVectorStoreKey
from graphrag.query.indexer_adapters import (
    read_indexer_entities,
    read_indexer_relationships,
    read_indexer_reports,
    read_indexer_text_units,
)
from graphrag.query.input.loaders.dfs import store_entity_semantic_embeddings
from graphrag.query.llm.oai.chat_openai import ChatOpenAI
from graphrag.query.llm.oai.embedding import OpenAIEmbedding
from graphrag.query.llm.oai.typing import OpenaiApiType
from graphrag.query.structured_search.local_search.mixed_context import LocalSearchMixedContext
from graphrag.query.structured_search.local_search.search import LocalSearch
from graphrag.vector_stores.lancedb import LanceDBVectorStore

# 配置日志
logger = logging.getLogger(__name__)


class QAService:
    _instance = None
    _initialized = False
    _ready = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 初始化基础配置（从settings读取）
            cls._instance._init_base_config()
            # 启动时自动尝试初始化
            import threading
            threading.Thread(target=cls._instance._auto_initialize_on_startup, daemon=True).start()
        return cls._instance

    def _auto_initialize_on_startup(self):
        """服务启动时自动检查并加载已有数据"""
        logger.info("启动时自动检查数据文件...")
        # 从settings读取路径
        if self.INPUT_DIR.exists():
            # 检查核心文件是否存在
            required_files = [
                self.INPUT_DIR / f"{self.TABLES['ENTITY_TABLE']}.parquet",
                self.INPUT_DIR / f"{self.TABLES['ENTITY_EMBEDDING_TABLE']}.parquet",
                self.INPUT_DIR / f"{self.TABLES['RELATIONSHIP_TABLE']}.parquet",
                self.INPUT_DIR / f"{self.TABLES['COMMUNITY_REPORT_TABLE']}.parquet",
                self.INPUT_DIR / f"{self.TABLES['TEXT_UNIT_TABLE']}.parquet",
            ]
            all_exist = all(file_path.exists() for file_path in required_files)

            if all_exist:
                logger.info("检测到已有数据文件，自动初始化QA服务...")
                self.initialize()  # 自动加载
            else:
                logger.info("检测到artifacts目录，但缺少核心文件，保持未就绪状态")
        else:
            logger.info("未检测到artifacts目录，保持未就绪状态")

    def _init_base_config(self):
        """仅初始化路径配置，从settings读取所有配置项"""
        # 路径配置（适配Pathlib）
        self.INPUT_DIR = settings.GRAPHRAG_FOLDER
        self.LANCEDB_URI = settings.LANCEDB_URI

        # 数据表名配置
        self.TABLES = settings.GRAPHRAG_TABLES

        # LLM配置
        self.LLM_CONFIG = settings.LLM_CONFIG['default']
        self.COMMUNITY_LEVEL = self.LLM_CONFIG['COMMUNITY_LEVEL']

        # 初始化空属性
        self.entities = None
        self.relationships = None
        self.reports = None
        self.text_units = None
        self.description_embedding_store = None
        self.llm = None
        self.text_embedder = None
        self.token_encoder = None
        self.context_builder = None
        self.search_engine = None

    def initialize(self):
        """手动初始化（上传文件后调用），启动时也会自动调用"""
        if self._ready:
            logger.info("QA服务已就绪，无需重复初始化")
            return True

        logger.info("开始手动初始化QA服务...")
        try:
            # 1. 检查目录和文件是否存在
            if not self.INPUT_DIR.exists():
                logger.warning(f"数据目录不存在: {self.INPUT_DIR}")
                return False

            required_files = [
                self.INPUT_DIR / f"{self.TABLES['ENTITY_TABLE']}.parquet",
                self.INPUT_DIR / f"{self.TABLES['ENTITY_EMBEDDING_TABLE']}.parquet",
                self.INPUT_DIR / f"{self.TABLES['RELATIONSHIP_TABLE']}.parquet",
                self.INPUT_DIR / f"{self.TABLES['COMMUNITY_REPORT_TABLE']}.parquet",
                self.INPUT_DIR / f"{self.TABLES['TEXT_UNIT_TABLE']}.parquet",
            ]

            missing_files = []
            for file_path in required_files:
                if not file_path.exists():
                    missing_files.append(str(file_path))

            if missing_files:
                logger.error(f"缺少必要的数据文件: {missing_files}")
                return False

            # 2. 加载数据
            self._load_data()

            # 3. 初始化LLM和嵌入模型
            self._init_llm()

            # 4. 初始化搜索引擎
            self._init_search_engine()

            self._ready = True
            logger.info("QA服务手动初始化完成，已就绪")
            return True

        except Exception as e:
            logger.error(f"QA服务初始化失败: {e}", exc_info=True)
            self._ready = False
            return False

    def _load_data(self):
        """加载数据（仅在手动初始化时执行）"""
        logger.info("加载实体数据...")
        entity_df = pd.read_parquet(self.INPUT_DIR / f"{self.TABLES['ENTITY_TABLE']}.parquet")
        entity_embedding_df = pd.read_parquet(self.INPUT_DIR / f"{self.TABLES['ENTITY_EMBEDDING_TABLE']}.parquet")
        self.entities = read_indexer_entities(entity_df, entity_embedding_df, self.COMMUNITY_LEVEL)

        self.description_embedding_store = LanceDBVectorStore(collection_name="default-entity-description")
        self.description_embedding_store.connect(db_uri=str(self.LANCEDB_URI))  # 转字符串兼容
        store_entity_semantic_embeddings(entities=self.entities, vectorstore=self.description_embedding_store)

        logger.info("加载关系数据...")
        relationship_df = pd.read_parquet(self.INPUT_DIR / f"{self.TABLES['RELATIONSHIP_TABLE']}.parquet")
        self.relationships = read_indexer_relationships(relationship_df)

        logger.info("加载报告数据...")
        report_df = pd.read_parquet(self.INPUT_DIR / f"{self.TABLES['COMMUNITY_REPORT_TABLE']}.parquet")
        self.reports = read_indexer_reports(report_df, entity_df, self.COMMUNITY_LEVEL)

        logger.info("加载文本单元数据...")
        text_unit_df = pd.read_parquet(self.INPUT_DIR / f"{self.TABLES['TEXT_UNIT_TABLE']}.parquet")
        self.text_units = read_indexer_text_units(text_unit_df)

    def _init_llm(self):
        """初始化LLM（从settings读取配置）"""
        logger.info("初始化LLM和嵌入模型...")
        # 从settings读取LLM配置
        llm_conf = self.LLM_CONFIG

        self.llm = ChatOpenAI(
            api_key=llm_conf['API_KEY'],
            model=llm_conf['LLM_MODEL'],
            api_base=llm_conf['API_BASE'],
            api_type=OpenaiApiType[llm_conf['API_TYPE']],  # 映射枚举值
            max_retries=20,
        )

        self.text_embedder = OpenAIEmbedding(
            api_key=llm_conf['API_KEY'],
            api_base=llm_conf['API_BASE'],
            api_type=OpenaiApiType[llm_conf['API_TYPE']],
            model=llm_conf['EMBEDDING_MODEL'],
            deployment_name=llm_conf['EMBEDDING_MODEL'],
            max_retries=20,
        )

        self.token_encoder = tiktoken.get_encoding(llm_conf['TOKEN_ENCODING'])

    def _init_search_engine(self):
        """初始化搜索引擎（从settings读取配置）"""
        logger.info("初始化搜索引擎...")
        llm_conf = self.LLM_CONFIG

        # 映射 EntityVectorStoreKey
        vectorstore_key = EntityVectorStoreKey.ID if llm_conf['LOCAL_CONTEXT_PARAMS'][
                                                         'embedding_vectorstore_key'] == 'id' else EntityVectorStoreKey.NAME

        self.context_builder = LocalSearchMixedContext(
            community_reports=self.reports,
            text_units=self.text_units,
            entities=self.entities,
            relationships=self.relationships,
            covariates=None,
            entity_text_embeddings=self.description_embedding_store,
            embedding_vectorstore_key=vectorstore_key,
            text_embedder=self.text_embedder,
            token_encoder=self.token_encoder,
        )

        self.search_engine = LocalSearch(
            llm=self.llm,
            context_builder=self.context_builder,
            token_encoder=self.token_encoder,
            llm_params=llm_conf['LLM_PARAMS'],
            context_builder_params=llm_conf['LOCAL_CONTEXT_PARAMS'],
            response_type=llm_conf['RESPONSE_TYPE'],
        )

    def is_ready(self):
        """检查服务是否就绪"""
        return self._ready

    def reload_data(self):
        """重新加载数据（上传文件后调用）"""
        logger.info("开始重新加载QA服务数据...")
        self._ready = False
        return self.initialize()

    async def query(self, question: str) -> str:
        """处理查询，返回纯Markdown文本"""
        if not self.is_ready():
            return "系统尚未就绪，请管理员先上传数据文件并完成导入"

        try:
            result = await self.search_engine.asearch(question)
            return result.response if result else "未找到相关答案"
        except Exception as e:
            logger.error(f"查询失败: {e}", exc_info=True)
            return f"查询处理失败，请稍后重试：{str(e)[:100]}"


# 实例化服务（创建对象后自动检查并加载）
qa_service = QAService()