from __future__ import annotations

from statistics import mean

from intervai.graph import InterviewGraph
from intervai.llm import LlmInterviewClient
from intervai.rag import HybridRetriever, KnowledgeHit
from intervai.resume import parse_resume_text
from intervai.schemas import InterviewSession, InterviewStage, InterviewTurn, new_session_id
from intervai.skills import SkillRegistry


QUESTION_BANK = {
    "backend": [
        "请设计一个短链接服务，你如何保证ID唯一并支撑高并发访问？",
        "如果接口延迟突然升高，你会如何定位并恢复服务？",
        "请设计一个订单创建接口，你如何保证幂等、事务一致性和可观测性？",
    ],
    "ai": [
        "请设计一个面向企业知识库的RAG问答服务，你如何降低幻觉？",
        "LangGraph适合解决哪些普通链式调用难处理的问题？请结合一个Agent工作流说明。",
        "如果向量检索召回不稳定，你会如何评估和优化？",
    ],
    "general": [
        "请介绍一个你最有代表性的项目，并说明你的关键贡献。",
        "讲一次你和他人意见冲突的经历，你是如何推进结果的？",
        "面对一个完全陌生的问题，你通常如何拆解和验证？",
    ],
}


class InterviewService:
    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        skills: SkillRegistry | None = None,
        llm_client: LlmInterviewClient | None = None,
    ) -> None:
        self.retriever = retriever or HybridRetriever()
        self.skills = skills or SkillRegistry()
        self.llm = llm_client or LlmInterviewClient()
        self.sessions: dict[str, InterviewSession] = {}
        self.graph = InterviewGraph()
        self.graph.add_step(InterviewStage.PREPARE, self._prepare)
        self.graph.add_step(InterviewStage.ASK, self._ask)
        self.graph.add_step(InterviewStage.EVALUATE, self._evaluate_latest_answer)
        self.graph.add_step(InterviewStage.SUMMARY, self._summarize)

    def create_session(
        self,
        resume_text: str,
        job_title: str,
        job_description: str = "",
        max_questions: int = 5,
    ) -> InterviewSession:
        session = InterviewSession(
            session_id=new_session_id(),
            job_title=job_title,
            resume_text=resume_text,
            job_description=job_description,
            max_questions=max(1, min(max_questions, 10)),
        )
        session = self.graph.run(session)
        self.sessions[session.session_id] = session
        return session

    def answer(self, session_id: str, answer: str) -> InterviewSession:
        session = self._get_session(session_id)
        if session.finished:
            return session
        if not session.turns:
            session.stage = InterviewStage.ASK
            session = self.graph.run(session)

        session.turns[-1].answer = answer
        session.stage = InterviewStage.EVALUATE
        session = self.graph.run(session)
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> InterviewSession:
        return self._get_session(session_id)

    def initialize_knowledge_base(self) -> bool:
        return self.retriever.initialize_vector_store()

    def _prepare(self, session: InterviewSession) -> InterviewSession:
        profile = parse_resume_text(session.resume_text)
        session.candidate_profile = profile
        skills = set(profile["skills"])
        job_text = f"{session.job_title} {session.job_description}".lower()

        if {"langchain", "langgraph", "rag", "llm", "agent"} & skills or "ai" in job_text:
            track = "ai"
        elif {"fastapi", "redis", "mysql", "go", "java", "python", "缓存", "系统设计"} & skills or "后端" in job_text:
            track = "backend"
        else:
            track = "general"

        session.competency_model = {
            "track": [track],
            "technical_depth": ["核心概念", "工程权衡", "边界条件"],
            "delivery": ["接口设计", "数据建模", "稳定性", "可观测性"],
            "communication": ["结构化表达", "澄清问题", "量化结果"],
            "learning_agility": ["复盘", "验证", "迭代"],
        }
        session.stage = InterviewStage.ASK
        return session

    def _ask(self, session: InterviewSession) -> InterviewSession:
        if session.asked_count >= session.max_questions:
            session.finished = True
            session.stage = InterviewStage.SUMMARY
            return session

        fallback_question = self._fallback_question(session)
        last_gap = _last_gap(session)
        hits = self.retriever.search(f"{session.job_title} {session.job_description} {fallback_question} {last_gap}")
        references = _format_hits(hits)
        question = self.llm.generate_question(
            job_title=session.job_title,
            job_description=session.job_description,
            resume_summary=str(session.candidate_profile.get("summary", "")),
            competency_model=session.competency_model,
            references=references,
            history=_history_for_prompt(session),
            last_gap=last_gap,
            fallback_question=fallback_question,
        )
        standard_answer = self.llm.generate_standard_answer(
            job_title=session.job_title,
            question=question,
            references=references,
            fallback_answer=_standard_answer(question, hits),
        )

        session.current_question = question
        session.turns.append(InterviewTurn(question=question, standard_answer=standard_answer, references=references))
        session.asked_count += 1
        session.stage = InterviewStage.ANSWER
        return session

    def _evaluate_latest_answer(self, session: InterviewSession) -> InterviewSession:
        turn = session.turns[-1]
        query = f"{session.job_title} {session.job_description} {turn.question} {turn.answer}"
        hits = self.retriever.search(query)
        references = _format_hits(hits)
        expected_terms = _expected_terms(turn.question, hits)
        matched = [term for term in expected_terms if term.lower() in turn.answer.lower()]
        missing = [term for term in expected_terms if term not in matched]
        score = min(100, 35 + len(matched) * 10 + min(len(turn.answer) // 28, 18))
        skill_result = self.skills.evaluate(turn.question, turn.answer)

        rule_evaluation = {
            "score": score,
            "matched_points": matched,
            "missing_points": missing[:6],
            "main_gap": missing[0] if missing else "",
            "needs_follow_up": bool(missing and score < 75 and session.asked_count < session.max_questions),
            "evidence": references[:3],
            "improvement_advice": _recommendations(missing)[:3],
            "comment": _comment(score),
            "source": "rules_fallback",
        }
        llm_evaluation = self.llm.evaluate_answer(
            job_title=session.job_title,
            question=turn.question,
            answer=turn.answer,
            references=references,
            rule_evaluation=rule_evaluation,
        )

        turn.references = references
        turn.skill_result = skill_result
        turn.evaluation = llm_evaluation or rule_evaluation
        if skill_result and not turn.evaluation.get("source") == "llm_rag":
            turn.evaluation["skill_evidence"] = skill_result

        if session.asked_count >= session.max_questions:
            turn.evaluation["needs_follow_up"] = False
            session.finished = True
            session.stage = InterviewStage.SUMMARY
        else:
            session.stage = InterviewStage.FOLLOW_UP if turn.evaluation.get("needs_follow_up") else InterviewStage.ASK
        return session

    def _summarize(self, session: InterviewSession) -> InterviewSession:
        scores = [turn.evaluation.get("score", 0) for turn in session.turns if turn.answer]
        avg_score = round(mean(scores), 1) if scores else 0
        weak_points: list[str] = []
        evidence: list[str] = []
        for turn in session.turns:
            weak_points.extend(turn.evaluation.get("missing_points", []))
            evidence.extend(turn.references)
        user_profile = _build_user_profile(session, weak_points, avg_score)
        session.user_profile = user_profile

        session.report = {
            "overall_score": avg_score,
            "llm_enabled": self.llm.available,
            "graph": "LangGraph StateGraph: prepare -> ask -> evaluate -> ask/summarize",
            "user_profile": user_profile,
            "improvement_backlog": user_profile["improvement_backlog"],
            "dimensions": {
                "technical_depth": _bounded(avg_score + 2),
                "delivery": _bounded(avg_score - 1),
                "problem_solving": _bounded(avg_score + 1),
                "communication": _bounded(avg_score - 2),
                "reflection": _bounded(avg_score - 4),
            },
            "weak_points": list(dict.fromkeys(weak_points))[:10],
            "evidence_sources": list(dict.fromkeys(evidence))[:8],
            "recommendations": _recommendations(weak_points),
            "next_practice": _next_practice(weak_points),
            "turn_reviews": [
                {
                    "question": turn.question,
                    "standard_answer": turn.standard_answer,
                    "score": turn.evaluation.get("score", 0),
                    "comment": turn.evaluation.get("comment", ""),
                    "evaluation_source": turn.evaluation.get("source", "rules_fallback"),
                    "matched_points": turn.evaluation.get("matched_points", []),
                    "missing_points": turn.evaluation.get("missing_points", []),
                    "improvement_advice": turn.evaluation.get("improvement_advice", []),
                    "skill_result": turn.skill_result,
                    "references": turn.references,
                }
                for turn in session.turns
                if turn.answer
            ],
        }
        session.stage = InterviewStage.SUMMARY
        return session

    def _fallback_question(self, session: InterviewSession) -> str:
        if session.turns and session.turns[-1].evaluation.get("needs_follow_up"):
            gap = session.turns[-1].evaluation.get("main_gap", "关键权衡")
            return f"追问：你刚才没有充分展开“{gap}”，请补充你的判断依据、落地方案和风险取舍。"

        track = session.competency_model.get("track", ["general"])[0]
        questions = QUESTION_BANK.get(track, QUESTION_BANK["general"])
        return questions[session.asked_count % len(questions)]

    def _get_session(self, session_id: str) -> InterviewSession:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"session not found: {session_id}") from exc


def _history_for_prompt(session: InterviewSession) -> list[dict[str, str]]:
    history = []
    for turn in session.turns:
        if not turn.answer:
            continue
        history.append({"question": turn.question, "answer": turn.answer})
    return history[-4:]


def _last_gap(session: InterviewSession) -> str:
    if not session.turns:
        return ""
    return str(session.turns[-1].evaluation.get("main_gap", ""))


def _format_hits(hits: list[KnowledgeHit]) -> list[str]:
    return [hit.as_reference() for hit in hits]


def _standard_answer(question: str, hits: list[KnowledgeHit]) -> str:
    expected = _expected_terms(question, hits)
    evidence_titles = [hit.title for hit in hits[:3]]
    lines = [
        "优秀回答应覆盖：",
        f"1. 先澄清目标、约束和边界条件，说明问题规模、成功指标和失败场景。",
        f"2. 围绕核心要点展开：{'、'.join(expected[:8])}。",
        "3. 给出可落地方案，包括关键组件、数据流、异常处理和降级策略。",
        "4. 说明工程权衡，例如一致性与性能、成本与准确率、复杂度与可维护性。",
        "5. 给出验证方式，例如测试用例、离线评测、监控指标或灰度方案。",
    ]
    if evidence_titles:
        lines.append(f"参考依据：{'、'.join(evidence_titles)}。")
    return "\n".join(lines)


def _expected_terms(question: str, hits: list[KnowledgeHit]) -> list[str]:
    base = ["边界条件", "权衡", "复杂度", "可观测性"]
    text = question + "\n" + "\n".join(hit.content for hit in hits)
    topic_terms = {
        "短链接": ["唯一ID", "缓存", "数据库", "限流", "过期策略", "容量估算"],
        "RAG": ["切分", "检索", "重排序", "引用", "评测", "幻觉"],
        "LangGraph": ["状态", "节点", "条件边", "检查点", "人工介入"],
        "FastAPI": ["请求模型", "错误处理", "异步", "健康检查", "鉴权"],
        "冲突": ["背景", "行动", "结果", "复盘"],
    }
    for topic, terms in topic_terms.items():
        if topic.lower() in text.lower():
            base.extend(terms)
    for hit in hits:
        for token in ["分布式", "监控", "索引", "STAR", "消息队列", "幂等", "一致性"]:
            if token in hit.content:
                base.append(token)
    return list(dict.fromkeys(base))


def _comment(score: int) -> str:
    if score >= 85:
        return "回答完整，有清晰权衡、落地步骤和风险意识。"
    if score >= 70:
        return "方向正确，但还需要补充关键细节、边界条件和可验证指标。"
    return "回答偏概括，需要把方案拆到可验证、可执行、可复盘的层面。"


def _bounded(score: float) -> int:
    return int(max(0, min(100, round(score))))


def _build_user_profile(session: InterviewSession, weak_points: list[str], avg_score: float) -> dict[str, object]:
    matched_points: list[str] = []
    answered_lengths: list[int] = []
    skill_signals: list[str] = []
    for turn in session.turns:
        if not turn.answer:
            continue
        matched_points.extend(turn.evaluation.get("matched_points", []))
        answered_lengths.append(len(turn.answer))
        if turn.skill_result:
            skill_signals.append(str(turn.skill_result.get("skill", "")))

    strengths = list(dict.fromkeys(matched_points))[:8] or ["能完成基础回答"]
    weakness_counts: dict[str, int] = {}
    for point in weak_points:
        weakness_counts[point] = weakness_counts.get(point, 0) + 1
    weakness_items = [
        {"point": point, "count": count, "advice": _recommendations([point])[0]}
        for point, count in sorted(weakness_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    ]
    avg_answer_length = round(mean(answered_lengths), 1) if answered_lengths else 0

    if avg_score >= 85:
        level = "ready"
        summary = "整体表现接近正式面试可用水平，重点是补齐少数高频追问。"
    elif avg_score >= 70:
        level = "promising"
        summary = "具备基础能力，但回答需要更多工程细节、边界条件和验证指标。"
    else:
        level = "needs_practice"
        summary = "当前回答偏概括，建议先训练结构化表达和核心知识点。"

    return {
        "level": level,
        "summary": summary,
        "target_role": session.job_title,
        "detected_skills": session.candidate_profile.get("skills", []),
        "strengths": strengths,
        "weaknesses": weakness_items,
        "answer_style": {
            "average_answer_length": avg_answer_length,
            "structure": "偏详细" if avg_answer_length > 120 else "偏简略",
            "skill_signals": list(dict.fromkeys(skill_signals)),
        },
        "improvement_backlog": [
            {
                "priority": index + 1,
                "topic": item["point"],
                "action": item["advice"],
            }
            for index, item in enumerate(weakness_items[:6])
        ],
    }


def _recommendations(weak_points: list[str]) -> list[str]:
    mapping = {
        "唯一ID": "复习Snowflake、号段模式和数据库唯一约束的取舍。",
        "缓存": "补充缓存穿透、击穿、雪崩和一致性策略。",
        "评测": "建立RAG离线评测集，跟踪召回率、准确率和引用质量。",
        "复杂度": "每道算法题固定补充时间/空间复杂度和失败用例。",
        "复盘": "行为面用STAR结构，并给出可量化结果。",
        "状态": "用LangGraph画出状态字段、节点输入输出和条件边。",
        "鉴权": "补充认证、授权、限流和审计日志的生产化设计。",
        "一致性": "梳理事务、本地消息表、重试和幂等之间的边界。",
    }
    result = [mapping[item] for item in weak_points if item in mapping]
    result.append("把每次模拟面试的弱项整理成学习清单，下次优先验证同类问题。")
    return list(dict.fromkeys(result))[:6]


def _next_practice(weak_points: list[str]) -> list[str]:
    if any(point in weak_points for point in ["RAG", "检索", "评测", "幻觉"]):
        return ["设计一个RAG离线评测方案，并说明如何定位召回差和生成差。"]
    if any(point in weak_points for point in ["缓存", "数据库", "一致性", "幂等"]):
        return ["设计一个订单创建接口，覆盖幂等、事务一致性、缓存和可观测性。"]
    if any(point in weak_points for point in ["复盘", "背景", "行动", "结果"]):
        return ["用STAR结构复盘一次项目延期或冲突处理经历。"]
    return ["重新回答本轮最低分问题，要求补充指标、边界条件和风险取舍。"]
