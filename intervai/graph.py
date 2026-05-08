from __future__ import annotations

from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from intervai.schemas import InterviewSession, InterviewStage


GraphStep = Callable[[InterviewSession], InterviewSession]


class InterviewGraphState(TypedDict):
    session: InterviewSession


class InterviewGraph:
    """LangGraph workflow for the interview lifecycle."""

    def __init__(self) -> None:
        self.steps: dict[InterviewStage, GraphStep] = {}
        self._compiled = None

    def add_step(self, stage: InterviewStage, step: GraphStep) -> None:
        self.steps[stage] = step
        self._compiled = None

    def run(self, session: InterviewSession) -> InterviewSession:
        app = self._compile()
        result = app.invoke({"session": session})
        return result["session"]

    def _compile(self):
        if self._compiled is not None:
            return self._compiled

        graph = StateGraph(InterviewGraphState)
        graph.add_node("prepare", self._node(InterviewStage.PREPARE))
        graph.add_node("ask", self._node(InterviewStage.ASK))
        graph.add_node("evaluate", self._node(InterviewStage.EVALUATE))
        graph.add_node("summarize", self._node(InterviewStage.SUMMARY))

        graph.add_conditional_edges(
            START,
            self._route_start,
            {
                "prepare": "prepare",
                "ask": "ask",
                "evaluate": "evaluate",
                "summarize": "summarize",
            },
        )
        graph.add_edge("prepare", "ask")
        graph.add_edge("ask", END)
        graph.add_conditional_edges(
            "evaluate",
            self._route_after_evaluate,
            {
                "ask": "ask",
                "summarize": "summarize",
            },
        )
        graph.add_edge("summarize", END)

        self._compiled = graph.compile()
        return self._compiled

    def _node(self, stage: InterviewStage):
        def run_step(state: InterviewGraphState) -> InterviewGraphState:
            session = state["session"]
            step = self.steps.get(stage)
            if step is None:
                return {"session": session}
            return {"session": step(session)}

        return run_step

    @staticmethod
    def _route_start(state: InterviewGraphState) -> str:
        stage = state["session"].stage
        if stage == InterviewStage.PREPARE:
            return "prepare"
        if stage == InterviewStage.EVALUATE:
            return "evaluate"
        if stage == InterviewStage.SUMMARY:
            return "summarize"
        return "ask"

    @staticmethod
    def _route_after_evaluate(state: InterviewGraphState) -> str:
        return "summarize" if state["session"].finished else "ask"
