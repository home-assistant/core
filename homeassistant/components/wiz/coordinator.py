"""DataUpdateCoordinator for the WiZ Platform integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from pywizlight import wizlight

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import WIZ_EXCEPTIONS

_LOGGER = logging.getLogger(__name__)

REQUEST_REFRESH_DELAY = 0.35


type WizConfigEntry = ConfigEntry[WizData]


@dataclass
class WizData:
    """Data for the wiz integration."""

    coordinator: WizCoordinator
    bulb: wizlight
    scenes: list


class WizCoordinator(DataUpdateCoordinator[float | None]):
    """Class to manage fetching WiZ data."""

    config_entry: WizConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WizConfigEntry,
        bulb: wizlight,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=15),
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )
        self._bulb = bulb

    async def _async_update_data(self) -> float | None:
        """Update the WiZ device."""
        ip_address = self._bulb.ip
        try:
            await self._bulb.updateState()
            if self._bulb.power_monitoring is not False:
                power: float | None = await self._bulb.get_power()
                return power
        except WIZ_EXCEPTIONS as ex:
            raise UpdateFailed(f"Failed to update device at {ip_address}: {ex}") from ex
        return None
