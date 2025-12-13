"""DataUpdateCoordinator for the Hegel integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from hegel_ip_client import COMMANDS, HegelClient, apply_state_changes
from hegel_ip_client.exceptions import HegelConnectionError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SLOW_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class HegelSlowPollCoordinator(DataUpdateCoordinator[None]):
    """Very slow fallback polling coordinator.

    This coordinator is only used to poll the device occasionally (slowly)
    to ensure state remains in sync if push updates are missed.
    """

    def __init__(
        self, hass: HomeAssistant, client: HegelClient, shared_state: dict[str, Any]
    ) -> None:
        """Initialize the slow poll coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="HegelSlowPoll",
            update_interval=timedelta(seconds=SLOW_POLL_INTERVAL),
        )
        self._client = client
        self._state = shared_state

    async def _async_update_data(self) -> None:
        """Periodically poll the amplifier to keep state in sync as a fallback."""
        for cmd in (
            COMMANDS["power_query"],
            COMMANDS["volume_query"],
            COMMANDS["mute_query"],
            COMMANDS["input_query"],
        ):
            try:
                update = await self._client.send(cmd, expect_reply=True, timeout=3.0)
                if update and update.has_changes():
                    apply_state_changes(
                        self._state, update, logger=_LOGGER, source="poll"
                    )
            except (HegelConnectionError, TimeoutError, OSError) as err:
                _LOGGER.error("Slow poll failed: %s", err)
                raise UpdateFailed(f"Error communicating with API: {err}") from err
