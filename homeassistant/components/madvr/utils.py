"""Utils for MadVR."""

from __future__ import annotations

from madvr.madvr import Madvr


async def cancel_tasks(client: Madvr) -> None:
    """Cancel all tasks."""
    if client.ping_task:
        client.ping_task.cancel()
    if client.heartbeat_task:
        client.heartbeat_task.cancel()


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""
