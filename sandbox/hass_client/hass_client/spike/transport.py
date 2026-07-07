"""In-process JSON transport that mimics a websocket round-trip.

The spike runs main and sandbox in one process. Direct ``await`` calls
between them would understate per-message cost. This transport instead:

- serializes each message with ``json.dumps`` (matches the wire format),
- pushes it through an ``asyncio.Queue`` (forces a loop yield, mimicking
  the schedule cost of a real WS),
- deserializes on the other side with ``json.loads`` before dispatching.

Both spike bridges share this transport so the comparison isolates
protocol shape — not network or framing — between Options A and B.
"""

import asyncio
from collections.abc import Awaitable, Callable
import contextlib
from itertools import count
import json
from typing import Any

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class InProcessTransport:
    """One-way RPC channel main → sandbox with awaited replies."""

    def __init__(self) -> None:
        """Create the transport with empty queues and no handler yet."""
        self._requests: asyncio.Queue[tuple[int, str, dict[str, Any]]] = asyncio.Queue()
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._handlers: dict[str, Handler] = {}
        self._ids = count(1)
        self._server_task: asyncio.Task[None] | None = None
        # Metrics: number of round-trips and total bytes serialized.
        self.message_count = 0
        self.byte_count = 0

    def register_handler(self, command: str, handler: Handler) -> None:
        """Register a sandbox-side handler for ``command``."""
        self._handlers[command] = handler

    async def start(self) -> None:
        """Start the server-side dispatch loop."""
        if self._server_task is None:
            self._server_task = asyncio.create_task(self._serve())

    async def stop(self) -> None:
        """Stop the dispatch loop."""
        if self._server_task is not None:
            self._server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._server_task
            self._server_task = None

    async def call(self, command: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a request and wait for the reply."""
        msg_id = next(self._ids)
        # Encode/decode to enforce the same serialization cost as a WS.
        encoded = json.dumps({"id": msg_id, "type": command, "payload": payload})
        self.message_count += 1
        self.byte_count += len(encoded)
        decoded = json.loads(encoded)
        future: asyncio.Future[dict[str, Any]] = (
            asyncio.get_running_loop().create_future()
        )
        self._pending[msg_id] = future
        await self._requests.put((decoded["id"], decoded["type"], decoded["payload"]))
        return await future

    async def _serve(self) -> None:
        """Dispatch incoming requests to registered handlers."""
        while True:
            msg_id, command, payload = await self._requests.get()
            handler = self._handlers.get(command)
            if handler is None:
                self._resolve(msg_id, {"error": f"unknown command {command!r}"})
                continue
            try:
                result = await handler(payload)
            except Exception as err:  # noqa: BLE001 — spike-level error surfacing
                self._resolve(msg_id, {"error": str(err)})
            else:
                # Round-trip the reply through JSON too — same cost both ways.
                encoded = json.dumps({"id": msg_id, "result": result})
                self.byte_count += len(encoded)
                self._resolve(msg_id, json.loads(encoded)["result"])

    def _resolve(self, msg_id: int, result: dict[str, Any]) -> None:
        """Resolve a pending future on the caller side."""
        future = self._pending.pop(msg_id, None)
        if future is not None and not future.done():
            future.set_result(result)
