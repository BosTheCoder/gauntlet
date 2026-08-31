"""The attack corpus.

One YAML file per family under `gauntlet/attacks/`, each holding a remediation note for
the family and a list of `{id, payload, note}` entries. Point `--attacks` at a directory of
your own to add families without touching the package.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Attack

BUILTIN_DIR = Path(__file__).parent / "attacks"
BUILTIN_FAMILIES = (
    "instruction_override",
    "role_confusion",
    "encoding",
    "tool_hijack",
    "exfiltration",
)


class AttackError(ValueError):
    """An attack file is malformed, or a suite asked for a family that is not loaded."""


def _load_file(path: Path) -> list[Attack]:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict) or not isinstance(raw.get("family"), str):
        raise AttackError(f"{path}: needs a family name")
    family = raw["family"]
    remediation = str(raw.get("remediation", "")).strip()
    entries = raw.get("attacks")
    if not isinstance(entries, list) or not entries:
        raise AttackError(f"{path}: needs a non-empty attacks list")
    out: list[Attack] = []
    for entry in entries:
        if not isinstance(entry, dict) or not {"id", "payload", "note"} <= set(entry):
            raise AttackError(f"{path}: each attack needs id, payload and note")
        out.append(
            Attack(
                id=str(entry["id"]),
                family=family,
                payload=str(entry["payload"]).strip(),
                note=str(entry["note"]).strip(),
                remediation=remediation,
            )
        )
    return out


def load_corpus(extra_dir: str | Path | None = None) -> list[Attack]:
    """Built-in families first, then any families found in `extra_dir`."""
    corpus: list[Attack] = []
    directories = [BUILTIN_DIR]
    if extra_dir is not None:
        path = Path(extra_dir)
        if not path.is_dir():
            raise AttackError(f"{path} is not a directory")
        directories.append(path)
    for directory in directories:
        for file in sorted(directory.glob("*.yaml")):
            corpus.extend(_load_file(file))
    ids = [a.id for a in corpus]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise AttackError(f"duplicate attack ids: {sorted(duplicates)}")
    return corpus


def select(corpus: list[Attack], families: list[str]) -> list[Attack]:
    """Attacks for the named families, ordered by the families list then by corpus order."""
    known = {a.family for a in corpus}
    missing = [f for f in families if f not in known]
    if missing:
        raise AttackError(f"unknown attack families: {missing}; corpus has {sorted(known)}")
    return [a for family in families for a in corpus if a.family == family]
