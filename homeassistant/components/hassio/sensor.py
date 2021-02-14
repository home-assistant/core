"""Sensor platform for Hass.io addons."""
from typing import Any, Callable, Dict, List

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from . import ADDONS_COORDINATOR, HassioAddonsDataUpdateCoordinator
from .const import ATTR_VERSION, ATTR_VERSION_LATEST
from .entity import HassioAddonEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Sensor set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    async_add_entities(
        [
            HassioAddonCurrentVersionEntity(coordinator, addon)
            for addon in coordinator.data.values()
        ]
        + [
            HassioAddonLatestVersionEntity(coordinator, addon)
            for addon in coordinator.data.values()
        ]
    )


class HassioAddonCurrentVersionEntity(HassioAddonEntity):
    """Binary sensor to track whether an update is available for a Hass.io add-on."""

    def __init__(
        self, coordinator: HassioAddonsDataUpdateCoordinator, addon: Dict[str, Any]
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, addon, "Current Version")

    @property
    def state(self) -> str:
        """Return state of entity."""
        return self.addon_info[ATTR_VERSION]


class HassioAddonLatestVersionEntity(HassioAddonEntity):
    """Binary sensor to track whether an update is available for a Hass.io add-on."""

    def __init__(
        self, coordinator: HassioAddonsDataUpdateCoordinator, addon: Dict[str, Any]
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, addon, "Latest Version")

    @property
    def state(self) -> str:
        """Return state of entity."""
        return self.addon_info[ATTR_VERSION_LATEST]
