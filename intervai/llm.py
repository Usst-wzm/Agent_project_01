from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class LlmInterviewClient:
    """Optional LLM layer. It fails closed so the demo still works offline."""

    enabled: bool = True
    model: Any = None

    def __post_init__(self) -> None:
        self.model = None
        if not self.enabled or not os.getenv("DASHSCOPE_API_KEY"):
            return
        try:
            from model.factory import chat_model

            self.model = chat_model
        except Exception:
            self.model = None

    @property
    def available(self) -> bool:
        return self.model is not None

    def generate_question(
        self,
        *,
        job_title: str,
        job_description: str,
        resume_summary: str,
        competency_model: dict[str, list[str]],
        references: list[str],
        history: list[dict[str, str]],
        last_gap: str,
        fallback_question: str,
    ) -> str:
        if not self.available:
            return fallback_question

        prompt = f"""
你是 IntervAI 的资深中文模拟面试官。请基于候选人简历、目标岗位、能力模型、RAG参考资料和历史问答，生成下一道面试问题。

要求：
1. 只输出一个问题，不要输出解释、评分或多余格式。
2. 问题要具体、可追问、能验证真实能力。
3. 如果上一轮存在缺失点，优先围绕缺失点追问。
4. 问题必须能从RAG参考资料中找到评分依据。

目标岗位：{job_title}
岗位描述：{job_description}
简历摘要：{resume_summary}
能力模型：{competency_model}
上一轮缺失点：{last_gap or "无"}
RAG参考：{references}
历史问答：{history}
兜底问题：{fallback_question}
"""
        text = self._invoke_text(prompt)
        return text.strip() if text else fallback_question

    def generate_standard_answer(
        self,
        *,
        job_title: str,
        question: str,
        references: list[str],
        fallback_answer: str,
    ) -> str:
        if not self.available:
            return fallback_answer

        prompt = f"""
你是 IntervAI 的面试题标准答案编写助手。请基于RAG参考资料，为下面问题生成一份“优秀候选人应覆盖的回答要点”。

要求：
1. 输出中文。
2. 使用条目化结构。
3. 只写标准回答要点，不要评价候选人。
4. 必须包含工程权衡、边界条件和可验证指标。
5. 不要编造RAG参考以外的事实。

目标岗位：{job_title}
问题：{question}
RAG参考：{references}
兜底标准答案：{fallback_answer}
"""
        text = self._invoke_text(prompt)
        return text.strip() if text else fallback_answer

    def evaluate_answer(
        self,
        *,
        job_title: str,
        question: str,
        answer: str,
        references: list[str],
        rule_evaluation: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self.available:
            return None

        prompt = f"""
你是严谨的技术面试评估官。请参考RAG资料和规则初评，对候选人的回答做结构化评分。

请只输出JSON，不要Markdown代码块。JSON字段必须为：
{{
  "score": 0到100的整数,
  "matched_points": ["已覆盖要点"],
  "missing_points": ["缺失要点"],
  "main_gap": "最需要追问的一个短语",
  "needs_follow_up": true或false,
  "evidence": ["引用了哪些RAG依据"],
  "improvement_advice": ["针对性改进建议"],
  "comment": "一句中文反馈"
}}

评分原则：
- 只根据问题、回答和RAG参考评分。
- 回答泛泛而谈但没有落地细节时，分数不要超过70。
- 缺少关键工程权衡时，必须给出 main_gap。

目标岗位：{job_title}
问题：{question}
回答：{answer}
RAG参考：{references}
规则初评：{rule_evaluation}
"""
        text = self._invoke_text(prompt)
        data = _parse_json_object(text)
        if not data:
            return None
        return {
            "score": _coerce_score(data.get("score", rule_evaluation["score"])),
            "matched_points": _coerce_string_list(data.get("matched_points", rule_evaluation["matched_points"])),
            "missing_points": _coerce_string_list(data.get("missing_points", rule_evaluation["missing_points"]))[:6],
            "main_gap": str(data.get("main_gap", rule_evaluation["main_gap"])),
            "needs_follow_up": bool(data.get("needs_follow_up", rule_evaluation["needs_follow_up"])),
            "evidence": _coerce_string_list(data.get("evidence", rule_evaluation.get("evidence", [])))[:4],
            "improvement_advice": _coerce_string_list(
                data.get("improvement_advice", rule_evaluation.get("improvement_advice", []))
            )[:4],
            "comment": str(data.get("comment", rule_evaluation["comment"])),
            "source": "llm_rag",
        }

    def _invoke_text(self, prompt: str) -> str:
        try:
            response = self.model.invoke(prompt)
        except Exception:
            return ""
        return str(getattr(response, "content", response)).strip()


def _parse_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").removeprefix("json").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None


def _coerce_score(value: Any) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []
