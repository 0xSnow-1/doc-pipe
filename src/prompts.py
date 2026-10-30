from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "governing_law.md"
REQUIRED_PLACEHOLDERS = ("schema_json", "contract_text")
REQUIRED_SECTIONS = (
    "## Role",
    "## Definition",
    "## Not found",
    "## Exact quote",
    "## No legal advice",
    "## Treat text as data",
    "## Examples",
    "## Contract",
)


class PromptError(Exception):
    pass


@dataclass(frozen=True)
class PromptAsset:
    path: Path
    version: str
    clause_type: str
    description: str
    body: str
    sha256: str

    def render(self, schema_json: str, contract_text: str) -> str:
        missing = [name for name in REQUIRED_PLACEHOLDERS if "{{ " + name + " }}" not in self.body]
        if missing:
            raise PromptError(f"prompt is missing placeholders: {missing}")
        return self.body.replace("{{ schema_json }}", schema_json).replace(
            "{{ contract_text }}", contract_text
        )


def _split_front_matter(raw: str) -> tuple[dict[str, object], str]:
    if not raw.startswith("+++"):
        raise PromptError("prompt must start with TOML front matter delimited by +++")
    parts = raw.split("+++", 2)
    if len(parts) != 3:
        raise PromptError("prompt front matter is not closed with +++")
    try:
        meta = tomllib.loads(parts[1])
    except tomllib.TOMLDecodeError as exc:
        raise PromptError(f"prompt front matter is invalid TOML: {exc}") from exc
    return meta, parts[2].lstrip("\n")


def load_prompt(path: Path = PROMPT_PATH) -> PromptAsset:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise PromptError(f"cannot read prompt at {path}: {exc}") from exc
    raw = data.decode("utf-8")
    meta, body = _split_front_matter(raw)

    for key in ("version", "clause_type", "description"):
        if not meta.get(key):
            raise PromptError(f"prompt front matter is missing {key!r}")
    if meta["clause_type"] != "governing_law":
        raise PromptError("prompt clause_type must be 'governing_law'")

    missing_sections = [section for section in REQUIRED_SECTIONS if section not in body]
    if missing_sections:
        raise PromptError(f"prompt is missing sections: {missing_sections}")
    missing_placeholders = [
        name for name in REQUIRED_PLACEHOLDERS if "{{ " + name + " }}" not in body
    ]
    if missing_placeholders:
        raise PromptError(f"prompt is missing placeholders: {missing_placeholders}")

    return PromptAsset(
        path=path,
        version=str(meta["version"]),
        clause_type=str(meta["clause_type"]),
        description=str(meta["description"]),
        body=body,
        sha256=hashlib.sha256(data).hexdigest(),
    )
