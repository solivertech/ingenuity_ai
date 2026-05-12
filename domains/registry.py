"""
Domain adapter registry.

load_adapter(domain_id) returns the DomainAdapter for the given domain.
New adapters should be registered in _REGISTRY below.
"""

from domains.base import DomainAdapter


def load_adapter(domain_id: str) -> DomainAdapter:
    """
    Return the DomainAdapter instance for the given domain_id.
    Raises KeyError if the domain is not registered.
    """
    # Import inside function to avoid circular imports at module load time.
    from domains.automotive.adapter import CarvanaAdapter

    _REGISTRY: dict[str, type[DomainAdapter]] = {
        "carvana_suvs": CarvanaAdapter,
    }

    if domain_id not in _REGISTRY:
        raise KeyError(
            f"Unknown domain_id '{domain_id}'. "
            f"Registered: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[domain_id]()
