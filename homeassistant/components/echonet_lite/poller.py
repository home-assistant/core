"""Helper that manages property notifications and polling."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

from pyhems import CONTROLLER_INSTANCE, ESV_GET, Frame, Property
from pyhems.runtime import HemsClient

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .coordinator import EchonetLiteCoordinator

_LOGGER = logging.getLogger(__name__)


class EchonetLitePropertyPoller:
    """Manage property notifications and fall back to periodic polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: EchonetLiteCoordinator,
        client: HemsClient,
        *,
        poll_interval: float,
    ) -> None:
        """Initialize the poller for the given config entry.

        Args:
            hass: Home Assistant instance.
            coordinator: ECHONET Lite coordinator.
            client: Runtime client.
            poll_interval: Polling interval in seconds.
        """
        self._hass = hass
        self._coordinator = coordinator
        self._client = client

        self._pending: set[str] = set()
        self._scheduled: dict[str, asyncio.TimerHandle] = {}
        self._unsub_coordinator = None
        self._unsub_interval = None

        self._unsub_coordinator = coordinator.async_add_listener(
            self._handle_coordinator_update
        )
        self._unsub_interval = async_track_time_interval(
            hass,
            self._handle_interval,
            timedelta(seconds=max(1, int(poll_interval))),
        )

    def stop(self) -> None:
        """Cancel listeners and scheduled callbacks."""

        if self._unsub_coordinator:
            self._unsub_coordinator()
            self._unsub_coordinator = None
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None
        for handle in self._scheduled.values():
            handle.cancel()
        self._scheduled.clear()
        self._pending.clear()

    @callback
    def _handle_coordinator_update(self) -> None:
        current = set(self._coordinator.data)
        # Drop pending requests for nodes that are gone
        for device_key in list(self._pending):
            if device_key not in current:
                self._pending.discard(device_key)
        # Cancel scheduled callbacks for nodes that are gone
        for device_key in list(self._scheduled):
            if device_key not in current:
                self._scheduled.pop(device_key).cancel()

    @callback
    def _handle_interval(self, _now: datetime) -> None:
        self._async_handle_interval()

    @callback
    def _async_handle_interval(self) -> None:
        for device_key, node in self._coordinator.data.items():
            if not node.poll_epcs:
                continue

            if device_key in self._pending or device_key in self._scheduled:
                continue

            self._schedule_request(device_key)

    def schedule_immediate_poll(self, device_key: str, *, delay: float = 1.0) -> None:
        """Schedule polling for a device earlier than the regular cadence.

        This is intended to be called after a Set operation so the UI reflects
        device state changes sooner.
        """
        if device_key not in self._coordinator.data:
            return

        # If a request is already in-flight, let it complete.
        if device_key in self._pending:
            return

        # Cancel any later scheduled request and replace with an earlier one.
        if handle := self._scheduled.pop(device_key, None):
            handle.cancel()

        delay = max(0.0, float(delay))
        if delay <= 0:
            self._schedule_request(device_key)
            return

        self._scheduled[device_key] = self._hass.loop.call_later(
            delay, self._scheduled_fire, device_key
        )

    def _scheduled_fire(self, device_key: str) -> None:
        # Remove the scheduled handle before we run.
        self._scheduled.pop(device_key, None)
        self._schedule_request(device_key)

    def _schedule_request(self, device_key: str) -> None:
        if device_key in self._pending:
            return
        self._pending.add(device_key)
        self._hass.async_create_task(self._async_request_node(device_key))

    async def _async_request_node(self, device_key: str) -> None:
        try:
            node = self._coordinator.data.get(device_key)
            if not node or not node.poll_epcs:
                return

            properties = [Property(epc=epc, edt=b"") for epc in node.poll_epcs]
            frame = Frame(
                seoj=CONTROLLER_INSTANCE,
                deoj=node.eoj,
                esv=ESV_GET,
                properties=properties,
            )
            _LOGGER.debug(
                "Sending 0x62 poll to node %s for EPCs: [%s]",
                device_key,
                " ".join(f"{epc:02X}" for epc in sorted(node.poll_epcs)),
            )
            sent = await self._client.async_send(node.node_id, frame)
            if not sent:
                _LOGGER.debug(
                    "Failed to poll node %s: address unknown",
                    device_key,
                )
        except OSError as err:
            _LOGGER.debug(
                "Failed to request properties for node %s: %s", device_key, err
            )
        finally:
            self._pending.discard(device_key)


__all__ = ["EchonetLitePropertyPoller"]
