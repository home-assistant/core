"""Push notification handling."""

import asyncio
from collections.abc import Callable
from datetime import datetime

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util.uuid import random_uuid_hex

PUSH_CONFIRM_TIMEOUT = 10  # seconds

# Consecutive confirm timeouts after which the channel is considered degraded
# and cloud-capable targets are routed straight to cloud instead of waiting
# out the confirm timeout for every message.
PUSH_DEGRADED_AFTER_TIMEOUTS = 2

# How long a degraded channel routes via cloud before the next send probes
# local delivery again.
PUSH_DEGRADED_PROBE_INTERVAL = 300  # seconds


class PushChannel:
    """Class that represents a push channel."""

    def __init__(
        self,
        hass: HomeAssistant,
        webhook_id: str,
        support_confirm: bool,
        send_message: Callable[[dict], None],
        on_teardown: Callable[[], None],
    ) -> None:
        """Initialize a local push channel."""
        self.hass = hass
        self.webhook_id = webhook_id
        self.support_confirm = support_confirm
        self._send_message = send_message
        self.on_teardown = on_teardown
        self.pending_confirms: dict[str, dict] = {}
        self._consecutive_timeouts = 0
        self._degraded = False
        self._unsub_degraded_probe: CALLBACK_TYPE | None = None

    @property
    def degraded(self) -> bool:
        """Return if sends should be routed via cloud where possible."""
        return self._degraded

    @callback
    def async_send_notification(self, data, fallback_send):
        """Send a push notification."""
        if not self.support_confirm:
            self._send_message(data)
            return

        confirm_id = random_uuid_hex()
        data["hass_confirm_id"] = confirm_id

        async def handle_push_failed(_=None):
            """Fall back to cloud for a local push left unconfirmed in time."""
            # Already popped by a confirm or a teardown flush; nothing to fall back.
            if self.pending_confirms.pop(confirm_id, None) is None:
                return

            # A teardown flush is not a delivery failure of a live channel
            if self.on_teardown is not None:
                self._consecutive_timeouts += 1
                if self._consecutive_timeouts >= PUSH_DEGRADED_AFTER_TIMEOUTS:
                    self._async_mark_degraded()

            await fallback_send(data)

        self.pending_confirms[confirm_id] = {
            "unsub_scheduled_push_failed": async_call_later(
                self.hass, PUSH_CONFIRM_TIMEOUT, handle_push_failed
            ),
            "handle_push_failed": handle_push_failed,
        }
        self._send_message(data)

    @callback
    def async_confirm_notification(self, confirm_id) -> bool:
        """Confirm a push notification.

        Returns if confirmation successful.
        """
        if confirm_id not in self.pending_confirms:
            return False

        self.pending_confirms.pop(confirm_id)["unsub_scheduled_push_failed"]()
        # A timely confirm proves the channel delivers
        self._consecutive_timeouts = 0
        self._async_clear_degraded()
        return True

    @callback
    def _async_mark_degraded(self) -> None:
        """Route cloud-capable sends via cloud until a probe is confirmed."""
        self._degraded = True
        if self._unsub_degraded_probe is None:
            self._unsub_degraded_probe = async_call_later(
                self.hass, PUSH_DEGRADED_PROBE_INTERVAL, self._async_allow_probe
            )

    @callback
    def _async_allow_probe(self, _now: datetime) -> None:
        """Let the next send probe local delivery again."""
        self._unsub_degraded_probe = None
        self._degraded = False

    @callback
    def _async_clear_degraded(self) -> None:
        """Restore local delivery for all sends."""
        if self._unsub_degraded_probe is not None:
            self._unsub_degraded_probe()
            self._unsub_degraded_probe = None
        self._degraded = False

    async def async_teardown(self):
        """Tear down this channel."""
        # Tear down is in progress
        if self.on_teardown is None:
            return

        self.on_teardown()
        self.on_teardown = None
        self._async_clear_degraded()

        cancel_pending_local_tasks = [
            actions["handle_push_failed"]()
            for actions in self.pending_confirms.values()
        ]

        if cancel_pending_local_tasks:
            await asyncio.gather(*cancel_pending_local_tasks)
