from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class InterviewStage(str, Enum):
    PREPARE = "prepare"
    ASK = "ask"
    ANSWER = "answer"
    EVALUATE = "evaluate"
    FOLLOW_UP = "follow_up"
    SUMMARY = "summary"


@dataclass(slots=True)
class InterviewTurn:
    question: str
    answer: str = ""
    standard_answer: str = ""
    evaluation: dict[str, Any] = field(default_factory=dict)
    references: list[str] = field(default_factory=list)
    skill_result: dict[str, Any] | None = None


@dataclass(slots=True)
class InterviewSession:
    session_id: str
    job_title: str
    resume_text: str
    job_description: str = ""
    stage: InterviewStage = InterviewStage.PREPARE
    candidate_profile: dict[str, Any] = field(default_factory=dict)
    competency_model: dict[str, list[str]] = field(default_factory=dict)
    turns: list[InterviewTurn] = field(default_factory=list)
    asked_count: int = 0
    max_questions: int = 5
    current_question: str = ""
    finished: bool = False
    report: dict[str, Any] | None = None
    user_profile: dict[str, Any] = field(default_factory=dict)


def new_session_id() -> str:
    return f"itv_{uuid4().hex[:12]}"
