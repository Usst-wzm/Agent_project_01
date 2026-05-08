from __future__ import annotations

import re
from collections import Counter


TECH_KEYWORDS = [
    "python",
    "java",
    "go",
    "fastapi",
    "django",
    "flask",
    "spring",
    "mysql",
    "postgresql",
    "redis",
    "kafka",
    "docker",
    "kubernetes",
    "langchain",
    "langgraph",
    "rag",
    "mcp",
    "llm",
    "agent",
    "微服务",
    "分布式",
    "向量数据库",
    "机器学习",
    "系统设计",
    "缓存",
    "消息队列",
]


def parse_resume_text(resume_text: str) -> dict[str, object]:
    normalized = resume_text.lower()
    skills = []
    for keyword in TECH_KEYWORDS:
        if keyword.lower() in normalized or keyword in resume_text:
            skills.append(keyword)

    projects = re.findall(r"(?:项目|project)[:：]?\s*(.{8,100})", resume_text, flags=re.IGNORECASE)
    words = re.findall(r"[\w\u4e00-\u9fff]+", resume_text.lower())
    frequent_terms = [term for term, _ in Counter(words).most_common(12) if len(term) > 1]

    return {
        "skills": sorted(set(skills)),
        "projects": projects[:5],
        "frequent_terms": frequent_terms,
        "summary": resume_text[:320],
    }
