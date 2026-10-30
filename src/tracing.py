from __future__ import annotations

import os
from collections.abc import Mapping


def tracing_enabled(env: Mapping[str, str] | None = None) -> bool:
    values = env if env is not None else os.environ
    flag = values.get("LANGSMITH_TRACING", "").strip().lower()
    key = values.get("LANGSMITH_API_KEY", "").strip()
    return flag == "true" and bool(key)


def configure_tracing(env: Mapping[str, str] | None = None) -> bool:
    values = env if env is not None else os.environ
    enabled = tracing_enabled(values)
    if enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = values["LANGSMITH_API_KEY"]
        project = values.get("LANGSMITH_PROJECT", "").strip()
        if project:
            os.environ["LANGCHAIN_PROJECT"] = project
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
    return enabled
