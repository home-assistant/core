"""The Waterkotte Heatpump integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pywaterkotte.ecotouch import Ecotouch, TagData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

UPDATE_INTERVAL = 10


class EcotouchCoordinator(DataUpdateCoordinator[dict[TagData, Any]]):
    """heatpump coordinator."""

    def __init__(self, heatpump: Ecotouch, hass: HomeAssistant) -> None:
        """Init coordinator."""
        self._heatpump = heatpump

        self.alltags: set[TagData] = set()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[TagData, Any]:
        """Fetch the latest data from the source."""
        tag_list = list(self.alltags)
        return await self.hass.async_add_executor_job(
            self._heatpump.read_values, tag_list
        )

    def get_tag_value(self, tag: TagData) -> StateType:
        """Return a tag value."""
        return self.data.get(tag, None)

    @property
    def heatpump(self) -> Ecotouch:
        """Heatpump api."""
        return self._heatpump


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Waterkotte Heatpump from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    def create_heatpump_instance(username: str, password: str) -> Ecotouch:
        heatpump = Ecotouch(entry.data.get("host"))
        heatpump.login(username, password)
        return heatpump

    heatpump = await hass.async_add_executor_job(
        create_heatpump_instance, entry.data["username"], entry.data["password"]
    )

    coordinator = EcotouchCoordinator(heatpump, hass)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
