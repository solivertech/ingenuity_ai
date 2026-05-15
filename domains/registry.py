"""
Domain adapter registry.

load_adapter(domain_id) returns a DomainAdapter for the given domain.

Lookup order:
  1. Built-in adapters registered in _REGISTRY (Python class per domain)
  2. Saved domain configs in domains/saved/<domain_id>.json via GenericAdapter

Any domain can be onboarded via the Domain Wizard, which saves a JSON config
and serves it through GenericAdapter. Built-in adapters are reserved for
domains that need custom URL construction or normalization beyond what the
config-driven GenericAdapter can express.
"""

from domains.base import DomainAdapter

# Built-in adapters — keyed by domain_id.
# Add entries here only when a domain genuinely needs custom code.
_BUILTIN_REGISTRY: dict[str, str] = {
    "carvana_suvs": "domains.automotive.adapter.CarvanaAdapter",
}


def load_adapter(domain_id: str) -> DomainAdapter:
    """
    Return the DomainAdapter instance for the given domain_id.
    Raises KeyError if the domain is not registered or has no saved config.
    """
    if domain_id in _BUILTIN_REGISTRY:
        import importlib
        module_path, cls_name = _BUILTIN_REGISTRY[domain_id].rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, cls_name)()

    from discovery.domain_config import load_config
    from domains.generic.adapter import GenericAdapter

    try:
        domain_config = load_config(domain_id)
        return GenericAdapter(domain_config)
    except FileNotFoundError:
        pass

    registered = list(_BUILTIN_REGISTRY.keys())
    raise KeyError(
        f"Unknown domain_id '{domain_id}'. "
        f"Built-in: {registered}. "
        f"Add via Domain Wizard to create a saved config."
    )
