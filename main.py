from __future__ import annotations

import os

import uvicorn

from intervai.api import app


def main() -> None:
    host = os.getenv("INTERVAI_HOST", "127.0.0.1")
    port = int(os.getenv("INTERVAI_PORT", "8000"))
    reload = os.getenv("INTERVAI_RELOAD", "true").lower() in {"1", "true", "yes", "on"}
    uvicorn.run("main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
