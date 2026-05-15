"""GDPR/cookie consent popup removal — clicks common accept buttons before scraping."""

import logging

log = logging.getLogger(__name__)

_SELECTORS = [
    "[id*='accept']", "[class*='accept']",
    "[id*='agree']", "[class*='agree']",
    "[id*='consent']", "[class*='consent']",
    "[data-testid*='accept']", "[data-testid*='consent']",
    "button[aria-label*='accept' i]", "button[aria-label*='agree' i]",
    "#onetrust-accept-btn-handler", ".cookie-accept",
]

_DISMISS_SCRIPT = """
(function() {
    const sels = %s;
    for (const sel of sels) {
        try {
            const el = document.querySelector(sel);
            if (el && el.offsetParent !== null) { el.click(); return true; }
        } catch(e) {}
    }
    return false;
})();
""" % str(_SELECTORS)


def dismiss_consent_popup(page) -> bool:
    """Attempt to click away a consent dialog. Returns True if a button was clicked."""
    try:
        result = page.evaluate(_DISMISS_SCRIPT)
        if result:
            log.debug("Consent popup dismissed")
        return bool(result)
    except Exception as exc:
        log.debug("Consent dismissal skipped: %s", exc)
        return False
