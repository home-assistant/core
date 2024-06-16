"""Utils for MadVR."""

from __future__ import annotations

from madvr.madvr import Madvr


async def cancel_tasks(client: Madvr) -> None:
    """Cancel all tasks."""
    client.ping_task.cancel()
    client.heartbeat_task.cancel()
