"""Support for NZBGet switches."""
from __future__ import annotations

from typing import Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import NZBGetEntity
from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import NZBGetDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up NZBGet sensor based on a config entry."""
    coordinator: NZBGetDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    switches = [
        NZBGetDownloadSwitch(
            coordinator,
            entry.entry_id,
            entry.data[CONF_NAME],
        ),
    ]

    async_add_entities(switches)


class NZBGetDownloadSwitch(NZBGetEntity, SwitchEntity):
    """Representation of a NZBGet download switch."""

    def __init__(
        self,
        coordinator: NZBGetDataUpdateCoordinator,
        entry_id: str,
        entry_name: str,
    ):
        """Initialize a new NZBGet switch."""
        self._unique_id = f"{entry_id}_download"

        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            name=f"{entry_name} Download",
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the switch."""
        return self._unique_id

    @property
    def is_on(self):
        """Return the state of the switch."""
        return not self.coordinator.data["status"].get("DownloadPaused", False)

    async def async_turn_on(self, **kwargs) -> None:
        """Set downloads to enabled."""
        await self.hass.async_add_executor_job(self.coordinator.nzbget.resumedownload)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Set downloads to paused."""
        await self.hass.async_add_executor_job(self.coordinator.nzbget.pausedownload)
        await self.coordinator.async_request_refresh()
