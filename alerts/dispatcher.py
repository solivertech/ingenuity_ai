"""
Alert dispatcher — routes triggered alert items to notification channels.

Implemented: email (Gmail OAuth2), webhook (HTTP POST), SMS (Twilio)
Stubbed:     push notifications
"""

import json
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


class AlertDispatcher:
    """Routes alert items to configured notification channels."""

    def __init__(self, channels: list[str] | None = None):
        # "email" is always included; "webhook" and "sms" are added automatically
        # when the profile carries webhook_url / sms_to configuration.
        self.channels = channels or ["email"]

    def dispatch(
        self,
        triggered_items: list[dict],
        profile,
        domain_config=None,
        llm_result=None,
    ) -> dict[str, bool]:
        """Send alerts. Returns {channel: success} for each attempted channel."""
        if not triggered_items:
            return {}

        effective = self._effective_channels(profile)
        results: dict[str, bool] = {}

        for channel in effective:
            try:
                if channel == "email":
                    results["email"] = self._send_email(
                        triggered_items, profile, domain_config, llm_result
                    )
                elif channel == "webhook":
                    results["webhook"] = self._send_webhook(
                        triggered_items, profile, domain_config
                    )
                elif channel == "sms":
                    results["sms"] = self._send_sms(
                        triggered_items, profile, domain_config
                    )
                else:
                    log.debug("Channel '%s' not implemented", channel)
                    results[channel] = False
            except Exception as exc:
                log.error("Dispatch failed for channel %s: %s", channel, exc)
                results[channel] = False

        return results

    # ── Channel detection ─────────────────────────────────────────────────────

    def _effective_channels(self, profile) -> list[str]:
        """Merge self.channels with any channels implied by the profile config."""
        channels = list(self.channels)
        if getattr(profile, "webhook_url", None) and "webhook" not in channels:
            channels.append("webhook")
        if getattr(profile, "sms_to", None) and "sms" not in channels:
            channels.append("sms")
        return channels

    # ── Email ─────────────────────────────────────────────────────────────────

    def _send_email(self, items, profile, domain_config, llm_result) -> bool:
        try:
            from notifications.email_alert import send_summary
            from analysis.llm import LLMResult

            result = llm_result or LLMResult(
                analysis=None, backend_used="none", model_used="",
                tokens_used=None, latency_ms=0, error=None,
            )
            return send_summary(
                items, result, [],
                trends={}, csv_path=None, force=True,
                new_vins=set(),
                email_to=profile.email_to,
                profile_label=profile.label,
                show_financing=False,
                down_payment=None,
                num_vehicles=1,
                domain_config=domain_config,
            )
        except Exception as exc:
            log.error("Email dispatch failed: %s", exc)
            return False

    # ── Webhook ───────────────────────────────────────────────────────────────

    def _send_webhook(self, items, profile, domain_config) -> bool:
        """POST a JSON alert payload to profile.webhook_url."""
        webhook_url = getattr(profile, "webhook_url", None)
        if not webhook_url:
            log.debug("No webhook_url on profile — skipping")
            return False

        payload = {
            "profile_id": getattr(profile, "profile_id", ""),
            "profile_label": getattr(profile, "label", ""),
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "item_count": len(items),
            "domain_id": getattr(profile, "domain_id", ""),
            "items": items,
        }

        try:
            import requests
            resp = requests.post(
                webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            log.info("Webhook dispatched to %s (%d items)", webhook_url, len(items))
            return True
        except Exception as exc:
            log.error("Webhook POST to %s failed: %s", webhook_url, exc)
            return False

    # ── SMS (Twilio) ──────────────────────────────────────────────────────────

    def _send_sms(self, items, profile, domain_config) -> bool:
        """Send an SMS summary via Twilio to each number in profile.sms_to."""
        sms_to = getattr(profile, "sms_to", None) or []
        if not sms_to:
            log.debug("No sms_to on profile — skipping")
            return False

        import os
        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
        from_number = os.getenv("TWILIO_FROM", "")

        if not all([account_sid, auth_token, from_number]):
            log.warning(
                "Twilio not configured — set TWILIO_ACCOUNT_SID, "
                "TWILIO_AUTH_TOKEN, TWILIO_FROM in .env"
            )
            return False

        body = self._sms_body(items, profile, domain_config)
        all_ok = True

        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            for number in sms_to:
                try:
                    msg = client.messages.create(
                        body=body,
                        from_=from_number,
                        to=number,
                    )
                    log.info("SMS sent to %s (SID: %s)", number, msg.sid)
                except Exception as exc:
                    log.error("SMS to %s failed: %s", number, exc)
                    all_ok = False
        except ImportError:
            log.error("twilio not installed — run: pip install twilio")
            return False

        return all_ok

    @staticmethod
    def _sms_body(items: list[dict], profile, domain_config) -> str:
        """Build a concise SMS message from the triggered items."""
        label = getattr(profile, "label", "Alert")
        count = len(items)
        domain = getattr(domain_config, "display_name", "") if domain_config else ""

        # Try to find a meaningful primary field to highlight
        primary_field = None
        if domain_config and getattr(domain_config, "fields", None):
            sort_fields = [f for f in domain_config.fields if getattr(f, "is_primary_sort", False)]
            if sort_fields:
                primary_field = sort_fields[0].name

        lines = [f"IngenuityAI — {label}"]
        if domain:
            lines[0] += f" ({domain})"
        lines.append(f"{count} new item{'s' if count != 1 else ''} found.")

        if items and primary_field:
            top = items[0]
            val = top.get(primary_field)
            title_field = next(
                (f.name for f in domain_config.fields
                 if f.data_type in ("str", "string") and not getattr(f, "is_primary_sort", False)),
                None,
            ) if domain_config and getattr(domain_config, "fields", None) else None
            title = top.get(title_field or "title") or top.get("name") or ""
            if title:
                lines.append(f"Top: {title}" + (f" — {val}" if val is not None else ""))

        return "\n".join(lines)
