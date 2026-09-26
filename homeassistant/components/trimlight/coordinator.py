"""Data coordinator for the Trimlight integration."""

from dataclasses import replace
import logging
from typing import override

from aiotrimlight import (
    TrimlightClient,
    TrimlightDeviceInfo,
    TrimlightError,
    TrimlightLightState,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


type TrimlightConfigEntry = ConfigEntry[TrimlightCoordinator]


class TrimlightCoordinator(DataUpdateCoordinator[TrimlightLightState]):
    """Coordinate runtime state polling for one Trimlight controller."""

    config_entry: TrimlightConfigEntry
    device_info: TrimlightDeviceInfo

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TrimlightConfigEntry,
        client: TrimlightClient,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    @override
    async def _async_setup(self) -> None:
        """Fetch data needed to set up entities."""
        try:
            self.device_info = await self.client.get_device_info()
        except TrimlightError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="setup_failed",
                translation_placeholders={
                    "error": str(err),
                    "name": self.config_entry.title,
                },
            ) from err

    @override
    async def _async_update_data(self) -> TrimlightLightState:
        """Fetch the current device state."""
        try:
            return await self.client.get_light_state()
        except TrimlightError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={
                    "error": str(err),
                    "name": self.config_entry.title,
                },
            ) from err

    async def async_set_state(
        self,
        *,
        on: bool,
        brightness: int | None = None,
        red: int | None = None,
        green: int | None = None,
        blue: int | None = None,
        warm_white: int | None = None,
        cold_white: int | None = None,
    ) -> None:
        """Publish requested changes immediately and let polling confirm them."""
        state = self.data
        self.async_set_updated_data(
            replace(
                state,
                is_on=on,
                brightness=state.brightness if brightness is None else brightness,
                red=state.red if red is None else red,
                green=state.green if green is None else green,
                blue=state.blue if blue is None else blue,
                warm_white=state.warm_white if warm_white is None else warm_white,
                cold_white=state.cold_white if cold_white is None else cold_white,
            )
        )

        try:
            await self.client.set_light_state(
                on=on,
                brightness=brightness,
                red=red,
                green=green,
                blue=blue,
                warm_white=warm_white,
                cold_white=cold_white,
            )
        except TrimlightError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "error": str(err),
                    "name": self.config_entry.title,
                },
            ) from err
