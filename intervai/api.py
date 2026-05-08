from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from intervai.service import InterviewService


class CreateInterviewRequest(BaseModel):
    resume_text: str = Field(..., min_length=10)
    job_title: str = Field(..., min_length=2)
    job_description: str = ""
    max_questions: int = Field(default=5, ge=1, le=10)


class AnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1)


service = InterviewService()
app = FastAPI(title="IntervAI", version="0.2.0")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>IntervAI</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, "Microsoft YaHei", Arial, sans-serif;
      color: #172033;
      background: #eef3f8;
    }
    * { box-sizing: border-box; }
    body { margin: 0; height: 100vh; overflow: hidden; }
    .shell { height: 100vh; display: grid; grid-template-columns: 340px minmax(0, 1fr); }
    aside { background: #ffffff; border-right: 1px solid #d9e2ee; padding: 22px; overflow: auto; }
    .brand { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 22px; }
    h1 { margin: 0; font-size: 24px; letter-spacing: 0; }
    h2 { margin: 22px 0 14px; font-size: 16px; }
    a { color: #1f6feb; text-decoration: none; }
    .chat { height: 100vh; display: grid; grid-template-rows: auto minmax(0, 1fr) auto; background: #f8fafc; }
    .chat-header {
      min-height: 76px; padding: 18px 24px; background: #ffffff; border-bottom: 1px solid #d9e2ee;
      display: flex; align-items: center; justify-content: space-between; gap: 16px;
    }
    .chat-title { font-size: 18px; font-weight: 800; }
    .messages { overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
    label { display: block; margin: 12px 0 6px; font-size: 14px; font-weight: 700; }
    input, textarea {
      width: 100%; border: 1px solid #c8d3e2; border-radius: 6px; padding: 10px 12px;
      font: inherit; background: #fbfdff;
    }
    textarea { min-height: 120px; resize: vertical; line-height: 1.5; }
    button {
      margin-top: 14px; border: 0; border-radius: 6px; padding: 10px 14px; font: inherit; font-weight: 700;
      cursor: pointer; background: #1f6feb; color: #fff;
    }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .muted { color: #667085; font-size: 13px; }
    .session-card { border: 1px solid #d9e2ee; border-radius: 8px; padding: 12px; background: #f8fafc; line-height: 1.6; white-space: pre-wrap; }
    .message { display: flex; gap: 10px; max-width: 900px; }
    .message.user { align-self: flex-end; flex-direction: row-reverse; }
    .avatar {
      width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; flex: 0 0 34px;
      font-weight: 800; color: #fff; background: #175cd3;
    }
    .message.user .avatar { background: #344054; }
    .bubble {
      border: 1px solid #d9e2ee; border-radius: 8px; padding: 12px 14px; background: #ffffff;
      line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere;
    }
    .message.user .bubble { background: #e8f1ff; border-color: #bdd7ff; }
    .meta { margin-top: 8px; color: #667085; font-size: 13px; }
    .references {
      margin-top: 10px; padding-top: 8px; border-top: 1px solid #edf1f7; color: #475467; font-size: 13px;
    }
    .composer {
      padding: 16px 24px 20px; background: #ffffff; border-top: 1px solid #d9e2ee;
      display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; align-items: end;
    }
    .composer textarea { min-height: 66px; max-height: 180px; }
    .composer button { min-width: 96px; height: 44px; margin: 0; }
    pre {
      white-space: pre-wrap; background: #101828; color: #e6edf6; padding: 12px; border-radius: 6px;
      overflow: auto; max-height: 420px; margin: 8px 0 0;
    }
    @media (max-width: 820px) {
      body { overflow: auto; }
      .shell { height: auto; grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid #d9e2ee; }
      .chat { height: calc(100vh - 420px); min-height: 560px; }
      .chat-header { padding: 16px; align-items: flex-start; flex-direction: column; }
      .messages { padding: 16px; }
      .composer { padding: 12px 16px; grid-template-columns: 1fr; }
      .composer button { width: 100%; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <div class="brand">
        <div>
          <h1>IntervAI</h1>
          <div class="muted">有证据依据的自适应模拟面试</div>
        </div>
        <a class="muted" href="/docs" target="_blank">API</a>
      </div>
      <label for="jobTitle">目标岗位</label>
      <input id="jobTitle" value="AI应用工程师" />
      <label for="maxQuestions">题目数量</label>
      <input id="maxQuestions" type="number" min="1" max="10" value="3" />
      <label for="resume">简历文本</label>
      <textarea id="resume">我熟悉 Python、FastAPI、LangChain、LangGraph、RAG 和 Agent 应用开发，做过企业知识库问答和后端接口服务。</textarea>
      <label for="jobDescription">岗位描述</label>
      <textarea id="jobDescription">负责 AI 应用后端、RAG 检索增强、Agent 工作流和服务化落地。</textarea>
      <button id="startBtn">开始面试</button>
      <h2>当前会话</h2>
      <div id="sessionInfo" class="session-card muted">尚未开始。</div>
    </aside>
    <section class="chat">
      <div class="chat-header">
        <div>
          <div class="chat-title">模拟面试</div>
          <div id="chatStatus" class="muted">创建面试后，面试官会基于知识库开始提问。</div>
        </div>
        <a class="muted" href="/health" target="_blank">Health</a>
      </div>
      <div id="messages" class="messages">
        <div class="message assistant">
          <div class="avatar">AI</div>
          <div class="bubble">你好，我是 IntervAI。先在左侧填写岗位和简历，然后点击“开始面试”。</div>
        </div>
      </div>
      <div class="composer">
        <textarea id="answer" placeholder="输入你的回答，按 Ctrl + Enter 提交..." disabled></textarea>
        <button id="answerBtn" disabled>发送</button>
      </div>
    </section>
  </div>
  <script>
    let sessionId = null;
    let lastAssistantQuestion = "";
    let reportRendered = false;
    const $ = (id) => document.getElementById(id);

    async function postJson(url, body = {}) {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }

    function appendMessage(role, content, meta = "", references = [], standardAnswer = "") {
      const messages = $("messages");
      const message = document.createElement("div");
      message.className = "message " + role;
      const avatar = document.createElement("div");
      avatar.className = "avatar";
      avatar.textContent = role === "user" ? "你" : "AI";
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      bubble.textContent = content;
      if (meta) {
        const metaNode = document.createElement("div");
        metaNode.className = "meta";
        metaNode.textContent = meta;
        bubble.appendChild(metaNode);
      }
      if (references.length) {
        const refNode = document.createElement("div");
        refNode.className = "references";
        refNode.textContent = "参考依据：" + references.slice(0, 3).join(" | ");
        bubble.appendChild(refNode);
      }
      if (standardAnswer) {
        const answerNode = document.createElement("div");
        answerNode.className = "references";
        answerNode.textContent = "标准回答要点：" + standardAnswer;
        bubble.appendChild(answerNode);
      }
      message.appendChild(avatar);
      message.appendChild(bubble);
      messages.appendChild(message);
      messages.scrollTop = messages.scrollHeight;
    }

    function appendReport(report) {
      if (reportRendered) return;
      reportRendered = true;
      const message = document.createElement("div");
      message.className = "message assistant";
      const avatar = document.createElement("div");
      avatar.className = "avatar";
      avatar.textContent = "AI";
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      const title = document.createElement("div");
      title.textContent = "面试结束，这是你的反馈报告：";
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(report, null, 2);
      bubble.appendChild(title);
      bubble.appendChild(pre);
      message.appendChild(avatar);
      message.appendChild(bubble);
      $("messages").appendChild(message);
      $("messages").scrollTop = $("messages").scrollHeight;
    }

    function latestAnsweredTurn(data) {
      const answered = data.turns.filter((turn) => turn.answer);
      return answered[answered.length - 1];
    }

    function latestOpenTurn(data) {
      return data.turns[data.turns.length - 1];
    }

    function renderSession(data) {
      sessionId = data.session_id;
      $("sessionInfo").textContent = "Session: " + sessionId + "\\nStage: " + data.stage + "\\n题目: " + data.asked_count + "/" + data.max_questions;
      $("chatStatus").textContent = data.finished ? "面试已结束，报告已生成。" : "正在进行：" + data.job_title;
      $("answer").disabled = data.finished;
      $("answerBtn").disabled = data.finished;
      const openTurn = latestOpenTurn(data);
      if (!data.finished && data.current_question && data.current_question !== lastAssistantQuestion) {
        lastAssistantQuestion = data.current_question;
        appendMessage("assistant", data.current_question, "", openTurn?.references || []);
      }
      if (data.finished && data.report) appendReport(data.report);
    }

    $("startBtn").addEventListener("click", async () => {
      $("startBtn").disabled = true;
      try {
        $("messages").innerHTML = "";
        lastAssistantQuestion = "";
        reportRendered = false;
        const data = await postJson("/interviews", {
          resume_text: $("resume").value,
          job_title: $("jobTitle").value,
          job_description: $("jobDescription").value,
          max_questions: Number($("maxQuestions").value || 3)
        });
        appendMessage("assistant", "面试已创建。我会根据你的简历、目标岗位和知识库动态提问。");
        renderSession(data);
        $("answerBtn").disabled = false;
        $("answer").disabled = false;
        $("answer").focus();
      } catch (error) {
        alert("创建失败：" + error.message);
      } finally {
        $("startBtn").disabled = false;
      }
    });

    $("answerBtn").addEventListener("click", async () => {
      if (!sessionId) return;
      const answer = $("answer").value.trim();
      if (!answer) {
        alert("请先输入回答。");
        return;
      }
      $("answerBtn").disabled = true;
      try {
        appendMessage("user", answer);
        const data = await postJson(`/interviews/${sessionId}/answers`, { answer });
        const turn = latestAnsweredTurn(data);
        if (turn?.evaluation) {
          const score = turn.evaluation.score ?? 0;
          const comment = turn.evaluation.comment ?? "";
          const missing = (turn.evaluation.missing_points ?? []).join("、") || "无";
          const source = turn.evaluation.source || "rules_fallback";
          appendMessage(
            "assistant",
            `本题初评：${comment}`,
            `得分 ${score} | 来源 ${source} | 待加强：${missing}`,
            turn.references || [],
            turn.standard_answer || ""
          );
        }
        $("answer").value = "";
        renderSession(data);
      } catch (error) {
        alert("提交失败：" + error.message);
      } finally {
        if (!$("answer").disabled) $("answerBtn").disabled = false;
      }
    });

    $("answer").addEventListener("keydown", (event) => {
      if (event.ctrlKey && event.key === "Enter" && !$("answerBtn").disabled) $("answerBtn").click();
    });
  </script>
</body>
</html>
"""


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "IntervAI"}


@app.post("/knowledge/initialize")
def initialize_knowledge() -> dict[str, bool]:
    return {"vector_store_initialized": service.initialize_knowledge_base()}


@app.post("/interviews")
def create_interview(payload: CreateInterviewRequest) -> dict[str, Any]:
    session = service.create_session(
        resume_text=payload.resume_text,
        job_title=payload.job_title,
        job_description=payload.job_description,
        max_questions=payload.max_questions,
    )
    return _serialize_session(session)


@app.post("/interviews/{session_id}/answers")
def submit_answer(session_id: str, payload: AnswerRequest) -> dict[str, Any]:
    try:
        session = service.answer(session_id, payload.answer)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_session(session)


@app.get("/interviews/{session_id}")
def get_interview(session_id: str) -> dict[str, Any]:
    try:
        session = service.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_session(session)


def _serialize_session(session) -> dict[str, Any]:
    data = asdict(session)
    data["stage"] = session.stage.value
    return data
