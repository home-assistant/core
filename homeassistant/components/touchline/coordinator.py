"""Data update coordinator for the Roth Touchline integration."""

from datetime import timedelta
import logging
from typing import override

from pytouchline_extended import (
    ControllerStatus,
    RoomStatus,
    TouchlineConnectionError,
    TouchlineController,
    TouchlineError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    UpdateFailedUnreachable,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=1)

type TouchlineConfigEntry = ConfigEntry[TouchlineCoordinator]


class TouchlineCoordinator(DataUpdateCoordinator[dict[str, RoomStatus]]):
    """Poll all thermostats on a Touchline controller, keyed by unique ID."""

    config_entry: TouchlineConfigEntry
    controller_status: ControllerStatus

    def __init__(self, hass: HomeAssistant, entry: TouchlineConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.controller = TouchlineController(url=entry.data[CONF_HOST])

    @override
    async def _async_update_data(self) -> dict[str, RoomStatus]:
        """Fetch the state of all thermostats from the controller."""
        try:
            state = await self.controller.fetch_async()
        except TouchlineConnectionError as err:
            raise UpdateFailedUnreachable(
                f"Touchline controller at {self.controller.url} cannot be reached"
            ) from err
        except TouchlineError as err:
            raise UpdateFailed(
                f"Error communicating with Touchline controller at {self.controller.url}"
            ) from err

        self.controller_status = state.controller
        rooms: dict[str, RoomStatus] = {}
        for room in state.rooms:
            if room.controller_id is None or room.device_id is None:
                raise UpdateFailed(
                    f"Touchline controller at {self.controller.url} returned no ID "
                    f"for device {room.index}"
                )
            rooms[f"{room.controller_id}_{room.device_id}"] = room
        return rooms
