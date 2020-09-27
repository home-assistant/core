"""Support for NZBGet switches."""
from typing import Callable, List, Optional

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
    async_add_entities: Callable[[List[Entity], bool], None],
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


class NZBGetDownloadSwitch(NZBGetEntity, Entity):
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
        value = self.coordinator.data["status"].get("DownloadPaused")

        if value is None:
            v12_value = self.coordinator.data["status"].get("ServerPaused", False)
            value = self.coordinator.data["status"].get("Download2Paused", v12_value)

        return value

    def turn_on(self, **kwargs) -> None:
        """Set downloads to enabled."""
        coordinator.nzbget.resumedownload()
        self.update()

    def turn_off(self, **kwargs) -> None:
        """Set downloads to paused."""
        coordinator.nzbget.pausedownload()
        self.update()
