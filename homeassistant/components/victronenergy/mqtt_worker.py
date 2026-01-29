"""Lightweight MQTT worker thread helper for Victron integration.

This module provides a simple queue-backed worker that executes blocking
paho-mqtt client calls from a dedicated background thread. It is intended
for fire-and-forget operations (publish/subscribe/unsubscribe) where the
caller does not need the return value.
"""

from __future__ import annotations

import contextlib
import logging
import queue
import threading
from typing import Any

_LOGGER = logging.getLogger(__name__)


class MqttWorker:
    """A minimal worker that executes blocking MQTT client methods.

    Usage:
      worker = MqttWorker(client)
      worker.start()
      worker.enqueue("publish", topic, payload, qos, retain, props)
      worker.stop()
    """

    def __init__(self, client: Any) -> None:
        """Initialize the MQTT worker with an unbounded queue."""
        self._client = client
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop_immediate_event = threading.Event()

    def start(self) -> None:
        """Start the worker thread."""
        if self._thread and self._thread.is_alive():
            return

        # Ensure immediate-stop flag is clear when starting
        self._stop_immediate_event.clear()

        def _run() -> None:
            while True:
                cmd, args, kwargs = self._queue.get()
                # If instructed to stop immediately, drop remaining items
                if self._stop_immediate_event.is_set():
                    # Mark this item as processed (dropped) and exit
                    with contextlib.suppress(Exception):
                        self._queue.task_done()
                    break

                try:
                    func = getattr(self._client, cmd, None)
                    if callable(func):
                        func(*args, **kwargs)
                    else:
                        _LOGGER.warning("MQTT client has no method %s", cmd)
                except Exception:
                    _LOGGER.exception("MQTT worker failed running %s", cmd)
                finally:
                    with contextlib.suppress(Exception):
                        self._queue.task_done()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def enqueue(self, cmd: str, *args: Any, **kwargs: Any) -> None:
        """Enqueue a command to be executed by the worker.

        `cmd` should be the method name on the paho-mqtt client (e.g. 'publish').
        """
        try:
            self._queue.put_nowait((cmd, args, kwargs))
        except queue.Full:
            _LOGGER.warning("MQTT worker queue full, dropping command %s", cmd)

    def stop(self) -> None:
        """Stop the worker thread and wait for it to exit."""
        if not self._thread:
            return

        # Signal immediate stop so the worker drops remaining queued items
        self._stop_immediate_event.set()

        # Enqueue a stop sentinel to unblock the worker (queue is unbounded)
        try:
            self._queue.put(("_stop", (), {}))
        except Exception:
            _LOGGER.exception("Failed to enqueue stop sentinel for MQTT worker")

        # Wait for the thread to exit (block until it does)
        self._thread.join()
        self._thread = None
