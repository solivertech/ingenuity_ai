"""
Domains router — AI schema discovery, domain listing, and domain deletion.

POST /domains/discover  — SSE stream: run SchemaAgent and save the result
GET  /domains           — list all saved domain configs
DELETE /domains/{id}    — delete a saved domain config
"""

import asyncio
import json
import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter(prefix="/domains", tags=["domains"])


# ── Request models ────────────────────────────────────────────────────────────

class DiscoverRequest(BaseModel):
    url: str
    user_request: str
    domain_id: str
    display_name: str
    max_retries: int = 2


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/discover")
async def discover_domain(req: DiscoverRequest):
    """
    Run SchemaAgent in a background thread and stream progress via SSE.

    Each SSE event is a JSON object:
      {"type": "log",    "message": "..."}
      {"type": "result", "config": {...}}
      {"type": "error",  "message": "..."}
    """
    return StreamingResponse(
        _discover_stream(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _discover_stream(req: DiscoverRequest):
    """Async generator that runs discovery in a thread and yields SSE events."""
    import config as app_config

    queue: asyncio.Queue[dict] = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _run():
        try:
            _queue_put(queue, loop, {"type": "log", "message": f"Fetching {req.url} ..."})

            from analysis.llm import LLMAnalyzer
            from discovery.schema_agent import SchemaAgent
            from discovery.domain_config import save_config

            llm = LLMAnalyzer()
            agent = SchemaAgent(llm)

            config = agent.discover(
                url=req.url,
                user_request=req.user_request,
                domain_id=req.domain_id,
                display_name=req.display_name,
            )

            if config is None:
                _queue_put(queue, loop, {
                    "type": "error",
                    "message": "Discovery failed: could not extract a schema from the page.",
                })
                return

            _queue_put(queue, loop, {
                "type": "log",
                "message": f"Discovered {len(config.fields)} fields. Validating against live data ...",
            })

            max_retries = getattr(app_config, "DISCOVERY_MAX_RETRIES", req.max_retries)
            config = agent.validate_and_refine(config, max_retries=max_retries)

            saved_path = save_config(config)
            _queue_put(queue, loop, {
                "type": "log",
                "message": f"Saved domain config to {saved_path.name}",
            })
            _queue_put(queue, loop, {
                "type": "result",
                "config": asdict(config),
            })

        except Exception as exc:
            log.exception("Discovery error for %s", req.url)
            _queue_put(queue, loop, {
                "type": "error",
                "message": f"Unexpected error: {exc}",
            })
        finally:
            _queue_put(queue, loop, None)  # sentinel

    asyncio.get_event_loop().run_in_executor(None, _run)

    while True:
        item = await queue.get()
        if item is None:
            break
        yield f"data: {json.dumps(item)}\n\n"


def _queue_put(queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, item) -> None:
    """Thread-safe enqueue from a worker thread into an asyncio Queue."""
    loop.call_soon_threadsafe(queue.put_nowait, item)


@router.get("")
def list_domains():
    """Return all saved domain configs sorted by domain_id."""
    from discovery.domain_config import list_configs
    configs = list_configs()
    return {"domains": [asdict(c) for c in configs]}


@router.delete("/{domain_id}")
def delete_domain(domain_id: str):
    """Delete a saved domain config by domain_id."""
    from discovery.domain_config import delete_config
    removed = delete_config(domain_id)
    if not removed:
        raise HTTPException(404, f"Domain '{domain_id}' not found")
    return {"deleted": domain_id}
