from pathlib import Path

from src.states import EXTRACTION_STATE_KEYS, ExtractionState, new_state


def test_state_keys() -> None:
    assert set(ExtractionState.__annotations__) == set(EXTRACTION_STATE_KEYS)


def test_new_state_defaults() -> None:
    state = new_state("/tmp/input.txt", "text")
    assert state["retries"] == 0
    assert state["errors"] == []
    assert state["fields"] is None
    assert state["text"] == "text"


def test_no_messages_state_import() -> None:
    source = Path("src/states.py").read_text()
    assert "MessagesState" not in source
