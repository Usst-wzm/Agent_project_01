from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Protocol


class InterviewSkill(Protocol):
    name: str

    def can_handle(self, question: str, answer: str) -> bool:
        ...

    def evaluate(self, question: str, answer: str) -> dict[str, object]:
        ...


@dataclass(slots=True)
class CodeExecutionSkill:
    name: str = "algo_code_execution"

    def can_handle(self, question: str, answer: str) -> bool:
        markers = ["def ", "class ", "```", "复杂度", "algorithm", "leetcode", "算法"]
        text = f"{question}\n{answer}".lower()
        return any(marker in text for marker in markers)

    def evaluate(self, question: str, answer: str) -> dict[str, object]:
        code = _extract_python_code(answer)
        if not code:
            return {"skill": self.name, "status": "skipped", "notes": ["未检测到可执行的Python代码片段。"]}

        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return {
                "skill": self.name,
                "status": "failed",
                "notes": [f"代码语法错误：第{exc.lineno}行 {exc.msg}"],
            }

        functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        return {
            "skill": self.name,
            "status": "passed_static_check",
            "notes": ["代码通过AST静态解析。", f"检测到函数：{', '.join(functions) if functions else '无'}"],
        }


@dataclass(slots=True)
class SystemDesignSkill:
    name: str = "system_design"

    def can_handle(self, question: str, answer: str) -> bool:
        text = f"{question} {answer}"
        return any(term in text for term in ["设计", "架构", "系统", "容量", "高并发", "缓存", "数据库", "短链接"])

    def evaluate(self, question: str, answer: str) -> dict[str, object]:
        dimensions = {
            "api": ["接口", "API", "REST", "请求"],
            "data": ["数据库", "表", "索引", "存储"],
            "scale": ["缓存", "队列", "分布式", "扩容", "高并发"],
            "reliability": ["监控", "降级", "限流", "容灾", "一致性"],
        }
        covered = [name for name, terms in dimensions.items() if any(term in answer for term in terms)]
        missing = [name for name in dimensions if name not in covered]
        return {
            "skill": self.name,
            "status": "analyzed",
            "covered_dimensions": covered,
            "missing_dimensions": missing,
        }


@dataclass(slots=True)
class BehavioralSkill:
    name: str = "behavior_star"

    def can_handle(self, question: str, answer: str) -> bool:
        return any(term in question for term in ["冲突", "合作", "失败", "挑战", "行为", "经历", "复盘"])

    def evaluate(self, question: str, answer: str) -> dict[str, object]:
        star = {
            "situation": ["背景", "当时", "场景"],
            "task": ["目标", "任务", "负责"],
            "action": ["我做", "推进", "解决", "沟通"],
            "result": ["结果", "提升", "降低", "%", "复盘"],
        }
        covered = [name for name, terms in star.items() if any(term in answer for term in terms)]
        return {"skill": self.name, "status": "analyzed", "star_coverage": covered}


class SkillRegistry:
    def __init__(self) -> None:
        self.skills: list[InterviewSkill] = [CodeExecutionSkill(), SystemDesignSkill(), BehavioralSkill()]

    def evaluate(self, question: str, answer: str) -> dict[str, object] | None:
        for skill in self.skills:
            if skill.can_handle(question, answer):
                result = skill.evaluate(question, answer)
                result["evaluation_source"] = "skill_result"
                return result
        return None


def _extract_python_code(answer: str) -> str:
    if "```" not in answer:
        return answer if "def " in answer or "class " in answer else ""

    chunks = answer.split("```")
    for index, chunk in enumerate(chunks):
        if index % 2 == 1:
            code = chunk.removeprefix("python").strip()
            if code:
                return code
    return ""
