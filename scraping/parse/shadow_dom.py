"""Shadow DOM flattening — injects JS to expose shadow trees in the main document."""

import logging

log = logging.getLogger(__name__)

_FLATTEN_SCRIPT = """
(function flatten(root) {
    root.querySelectorAll('*').forEach(el => {
        if (el.shadowRoot) {
            const wrap = document.createElement('div');
            wrap.setAttribute('data-shadow-host', el.tagName.toLowerCase());
            wrap.innerHTML = el.shadowRoot.innerHTML;
            el.appendChild(wrap);
            flatten(el.shadowRoot);
        }
    });
})(document);
"""


def flatten_shadow_dom(page) -> None:
    """Inject JS to flatten Shadow DOM trees. Safe to call even if no shadow roots exist."""
    try:
        page.evaluate(_FLATTEN_SCRIPT)
        log.debug("Shadow DOM flattened")
    except Exception as exc:
        log.debug("Shadow DOM flatten skipped: %s", exc)
