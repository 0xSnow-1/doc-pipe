from typing import Any, TypedDict

EXTRACTION_STATE_KEYS = ("path", "text", "fields", "errors", "retries")


class ExtractionState(TypedDict, total=False):
    path: str
    text: str
    fields: dict[str, Any] | None
    errors: list[dict[str, Any]]
    retries: int


def new_state(path: str, text: str = "") -> ExtractionState:
    return {
        "path": path,
        "text": text,
        "fields": None,
        "errors": [],
        "retries": 0,
    }
