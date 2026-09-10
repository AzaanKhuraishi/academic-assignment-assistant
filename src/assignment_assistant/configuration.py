"""Small, strict configuration reader for the product's flat YAML file."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "jurisdiction": "UK",
    "academic_level": "postgraduate",
    "discipline": "auto",
    "citation_style": "auto",
    "human_approval": True,
    "max_autonomous_retries": 3,
    "external_research": "ask",
    "runtime_adapter": "codex",
}

ALLOWED_DISCIPLINES = {
    "auto",
    "generic",
    "consultancy",
    "cybersecurity",
    "cryptography",
    "humanities",
}


class ConfigurationError(ValueError):
    pass


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if lowered in {"null", "none", "~"}:
        return None
    try:
        return int(value)
    except ValueError:
        return value


def load_config(path: Path) -> Dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    if not path.exists():
        validate_config(config)
        return config

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ConfigurationError(
                f"{path}:{line_number}: expected a flat 'key: value' entry"
            )
        key, value = line.split(":", 1)
        key = key.strip()
        if key not in DEFAULT_CONFIG:
            raise ConfigurationError(f"{path}:{line_number}: unknown key '{key}'")
        config[key] = _parse_scalar(value)

    validate_config(config)
    return config


def validate_config(config: Dict[str, Any]) -> None:
    discipline = str(config.get("discipline", "auto")).lower()
    if discipline not in ALLOWED_DISCIPLINES:
        raise ConfigurationError(
            "discipline must be one of: " + ", ".join(sorted(ALLOWED_DISCIPLINES))
        )
    retries = config.get("max_autonomous_retries")
    if not isinstance(retries, int) or isinstance(retries, bool) or retries < 0:
        raise ConfigurationError("max_autonomous_retries must be a non-negative integer")
    if config.get("external_research") not in {"ask", "allow", "deny"}:
        raise ConfigurationError("external_research must be ask, allow, or deny")
    if config.get("human_approval") is not True:
        raise ConfigurationError("human_approval must remain true in version 0.1")


def render_default_config() -> str:
    return """# Academic Assignment Assistant configuration
jurisdiction: UK
academic_level: postgraduate
discipline: auto
citation_style: auto
human_approval: true
max_autonomous_retries: 3
external_research: ask
runtime_adapter: codex
"""


def update_config_value(path: Path, key: str, value: str) -> None:
    if key not in DEFAULT_CONFIG:
        raise ConfigurationError(f"Unknown configuration key: {key}")
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    rendered = f"{key}: {value}"
    updated = False
    output = []
    for line in lines:
        if line.strip().startswith(f"{key}:"):
            output.append(rendered)
            updated = True
        else:
            output.append(line)
    if not updated:
        output.append(rendered)
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
