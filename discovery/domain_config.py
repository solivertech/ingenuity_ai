"""
DomainConfig persistence — save, load, and list domain configs from domains/saved/.

Domain configs are stored as JSON files so they are human-readable and
version-controllable alongside the codebase.
"""

import json
import logging
from dataclasses import asdict
from pathlib import Path

import config
from domains.base import DomainConfig, FieldSchema

log = logging.getLogger(__name__)


def _saved_dir() -> Path:
    path = Path(getattr(config, "DOMAINS_DIR", "domains/saved"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_config(domain_config: DomainConfig) -> Path:
    """Persist a DomainConfig to domains/saved/<domain_id>.json."""
    path = _saved_dir() / f"{domain_config.domain_id}.json"
    data = asdict(domain_config)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log.info("DomainConfig saved: %s", path)
    return path


def load_config(domain_id: str) -> DomainConfig:
    """Load a DomainConfig from domains/saved/<domain_id>.json. Raises FileNotFoundError if absent."""
    path = _saved_dir() / f"{domain_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No saved domain config for '{domain_id}' at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    fields = [FieldSchema(**f) for f in data.pop("fields", [])]
    return DomainConfig(fields=fields, **data)


def list_configs() -> list[DomainConfig]:
    """Return all saved DomainConfigs, sorted by domain_id."""
    configs = []
    for path in sorted(_saved_dir().glob("*.json")):
        try:
            configs.append(load_config(path.stem))
        except Exception as exc:
            log.warning("Could not load domain config %s: %s", path.name, exc)
    return configs


def delete_config(domain_id: str) -> bool:
    """Delete domains/saved/<domain_id>.json. Returns True if deleted, False if not found."""
    path = _saved_dir() / f"{domain_id}.json"
    if path.exists():
        path.unlink()
        log.info("DomainConfig deleted: %s", domain_id)
        return True
    return False
