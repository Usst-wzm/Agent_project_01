from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from langchain_core.documents import Document


DEFAULT_KNOWLEDGE = [
    {
        "title": "短链接系统设计",
        "source": "builtin://backend-short-url",
        "content": (
            "短链接服务应覆盖唯一ID生成、重定向链路、缓存、数据库索引、防刷、过期策略、"
            "监控告警和容量估算。分布式ID可使用号段、Snowflake或中心化发号器。"
        ),
    },
    {
        "title": "RAG工程评估",
        "source": "builtin://ai-rag",
        "content": (
            "RAG答案需要说明数据切分、向量检索、召回排序、引用溯源、权限隔离、离线评测和幻觉控制。"
            "评估时关注是否能把检索结果转化为可靠决策。"
        ),
    },
    {
        "title": "LangGraph工作流",
        "source": "builtin://ai-langgraph",
        "content": (
            "LangGraph适合有状态、多分支、可恢复的Agent流程。回答应覆盖状态定义、节点职责、条件边、"
            "检查点、错误恢复、人工介入和可观测性。"
        ),
    },
    {
        "title": "FastAPI生产化",
        "source": "builtin://backend-fastapi",
        "content": (
            "生产级FastAPI服务应有请求模型、错误处理、异步接口、健康检查、日志、鉴权、限流、"
            "会话存储、测试和可观测性。"
        ),
    },
    {
        "title": "行为面STAR",
        "source": "builtin://behavior-star",
        "content": (
            "行为面回答应包含Situation、Task、Action、Result，并体现个人贡献、权衡过程、复盘学习和可量化结果。"
        ),
    },
    {
        "title": "算法题评价",
        "source": "builtin://algo-rubric",
        "content": (
            "算法题评分关注复杂度分析、边界条件、可读性、测试用例和运行结果。追问常围绕优化空间和失败用例展开。"
        ),
    },
]


@dataclass(slots=True)
class KnowledgeHit:
    title: str
    content: str
    source: str
    score: float = 0.0

    def as_reference(self, max_chars: int = 220) -> str:
        content = self.content.replace("\n", " ").strip()
        if len(content) > max_chars:
            content = content[:max_chars].rstrip() + "..."
        return f"{self.title} | {self.source} | {content}"


class HybridRetriever:
    """Chroma-first retriever with deterministic keyword fallback."""

    def __init__(
        self,
        data_dir: str | Path = "data/interview_knowledge",
        persist_directory: str | Path = "chroma_db/intervai",
        collection_name: str = "intervai_interview_knowledge",
        k: int = 4,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self.k = k
        self.documents = self._load_keyword_documents()
        self.vector_store = self._try_init_vector_store()

    def search(self, query: str, k: int | None = None) -> list[KnowledgeHit]:
        top_k = k or self.k
        if self.vector_store is not None:
            hits = self._vector_search(query, top_k)
            if hits:
                return hits
        return self._keyword_search(query, top_k)

    def initialize_vector_store(self) -> bool:
        """Load local interview knowledge into Chroma when embeddings are available."""
        if not os.getenv("DASHSCOPE_API_KEY"):
            return False
        try:
            from langchain_chroma import Chroma
            from langchain_community.embeddings import DashScopeEmbeddings
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except Exception:
            return False

        docs = [
            Document(
                page_content=item["content"],
                metadata={"title": item["title"], "source": item["source"]},
            )
            for item in self.documents
        ]
        if not docs:
            return False

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=520,
            chunk_overlap=80,
            separators=["\n\n", "\n", "。", "；", "，", ".", "!", "?", " ", ""],
        )
        split_docs = splitter.split_documents(docs)
        embeddings = DashScopeEmbeddings(model="text-embedding-v4")
        self.vector_store = Chroma.from_documents(
            documents=split_docs,
            embedding=embeddings,
            collection_name=self.collection_name,
            persist_directory=str(self.persist_directory),
        )
        return True

    def _try_init_vector_store(self):
        if not os.getenv("DASHSCOPE_API_KEY"):
            return None
        if not (self.persist_directory / "chroma.sqlite3").exists():
            return None
        try:
            from langchain_chroma import Chroma
            from langchain_community.embeddings import DashScopeEmbeddings

            embeddings = DashScopeEmbeddings(model="text-embedding-v4")
            return Chroma(
                collection_name=self.collection_name,
                embedding_function=embeddings,
                persist_directory=str(self.persist_directory),
            )
        except Exception:
            return None

    def _vector_search(self, query: str, k: int) -> list[KnowledgeHit]:
        try:
            results = self.vector_store.similarity_search_with_relevance_scores(query, k=k)
        except Exception:
            return []

        hits: list[KnowledgeHit] = []
        for doc, score in results:
            title = str(doc.metadata.get("title") or doc.metadata.get("source") or "知识片段")
            source = str(doc.metadata.get("source") or "chroma")
            hits.append(KnowledgeHit(title=title, content=doc.page_content, source=source, score=float(score)))
        return hits

    def _keyword_search(self, query: str, k: int) -> list[KnowledgeHit]:
        terms = _tokenize(query)
        scored: list[KnowledgeHit] = []
        for item in self.documents:
            haystack = f"{item['title']} {item['content']}".lower()
            score = sum(2 if term in str(item["title"]).lower() else 1 for term in terms if term in haystack)
            if score:
                scored.append(
                    KnowledgeHit(
                        title=str(item["title"]),
                        content=str(item["content"]),
                        source=str(item["source"]),
                        score=float(score),
                    )
                )

        if not scored:
            scored = [
                KnowledgeHit(str(item["title"]), str(item["content"]), str(item["source"]), 0.0)
                for item in self.documents[:k]
            ]
        return sorted(scored, key=lambda hit: hit.score, reverse=True)[:k]

    def _load_keyword_documents(self) -> list[dict[str, str]]:
        documents = [dict(item) for item in DEFAULT_KNOWLEDGE]
        if not self.data_dir.exists():
            return documents

        for path in _iter_knowledge_files(self.data_dir):
            text = _read_text(path)
            if not text.strip():
                continue
            documents.append(
                {
                    "title": path.stem.replace("_", " "),
                    "source": str(path.as_posix()),
                    "content": text.strip(),
                }
            )
        return documents


def _iter_knowledge_files(root: Path) -> Iterable[Path]:
    for suffix in ("*.md", "*.txt"):
        yield from sorted(root.rglob(suffix))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="gbk", errors="ignore")


def _tokenize(query: str) -> list[str]:
    normalized = query.lower()
    for char in "/,，。；;:：()（）[]【】\n\t":
        normalized = normalized.replace(char, " ")
    terms = [term.strip() for term in normalized.split() if term.strip()]
    important = [
        "rag",
        "langgraph",
        "fastapi",
        "短链接",
        "star",
        "缓存",
        "数据库",
        "消息队列",
        "复杂度",
        "系统设计",
        "agent",
        "向量检索",
        "幻觉",
    ]
    terms.extend(term for term in important if term.lower() in normalized)
    return list(dict.fromkeys(terms))


SimpleRetriever = HybridRetriever
