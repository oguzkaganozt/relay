"""Relay privacy settings (stdlib only, Python 3.11+).

Two INDEPENDENT controls per V2 "Iki Acik Kontrol":
  cloud_processing  - transcript / action text sent to the remote model?
  context_sharing   - active window / app / title / selection added to the
                     model request?

Stored in ~/.config/relay/settings.toml (kept separate from config.toml so
groq/model config and runtime privacy toggles don't entangle). Defaults
match V2: cloud_processing on; context_sharing on ONLY after first-use
consent (context_sharing_consented=false until the user consents in the bar).

"Context sharing ayari Cloud processing ayarini sessizce degistirmez" -
the two are read independently and never mutate each other.
"""
from __future__ import annotations

import os
from pathlib import Path

XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
SETTINGS_PATH = XDG_CONFIG / "relay" / "settings.toml"

DEFAULTS = {
    "cloud_processing": True,
    "context_sharing": True,
    "context_sharing_consented": False,
}

_VALID = set(DEFAULTS)


def load(path: Path = SETTINGS_PATH) -> dict:
    """Return the privacy settings dict, filling DEFAULTS for anything missing
    or malformed. Never raises."""
    cfg = dict(DEFAULTS)
    if path.exists():
        try:
            import tomllib
            with open(path, "rb") as f:
                data = tomllib.load(f)
            sec = data.get("privacy", {})
            if isinstance(sec, dict):
                for k in DEFAULTS:
                    v = sec.get(k)
                    if isinstance(v, bool):
                        cfg[k] = v
        except Exception:
            pass
    return cfg


def _render(cfg: dict) -> str:
    out = ["# Relay privacy settings (managed by relay-bar Settings).",
           "# cloud_processing  - send transcript/action text to the remote model",
           "# context_sharing   - send active window/app/title/selection to the model",
           "# context_sharing_consented - set true after first-use consent",
           "[privacy]"]
    for k in ("cloud_processing", "context_sharing", "context_sharing_consented"):
        out.append(f"{k} = {'true' if cfg.get(k, DEFAULTS[k]) else 'false'}")
    return "\n".join(out) + "\n"


def save(cfg: dict, path: Path = SETTINGS_PATH) -> None:
    """Atomically write the [privacy] section. Unknown keys are dropped;
    missing keys fall back to DEFAULTS. Never raises."""
    clean = {k: bool(cfg.get(k, DEFAULTS[k])) for k in DEFAULTS}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".toml.tmp")
        tmp.write_text(_render(clean), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def cloud_processing_enabled(cfg: dict) -> bool:
    return bool(cfg.get("cloud_processing", DEFAULTS["cloud_processing"]))


def context_sharing_enabled(cfg: dict) -> bool:
    """True only when context_sharing is on AND the user has consented."""
    return (bool(cfg.get("context_sharing", DEFAULTS["context_sharing"]))
            and bool(cfg.get("context_sharing_consented", DEFAULTS["context_sharing_consented"])))


def consent_to_context_sharing(path: Path = SETTINGS_PATH) -> dict:
    """Record first-use consent and turn context sharing on. Returns the new cfg."""
    cfg = load(path)
    cfg["context_sharing"] = True
    cfg["context_sharing_consented"] = True
    save(cfg, path)
    return cfg
