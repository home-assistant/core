"""Binary sensor platform for Hass.io addons."""
from typing import Any, Callable, Dict, List

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from . import ADDONS_COORDINATOR, HassioAddonsDataUpdateCoordinator
from .const import ATTR_UPDATE_AVAILABLE
from .entity import HassioAddonEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Binary sensor set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    async_add_entities(
        [
            HassioAddonUpdateAvailableEntity(coordinator, addon)
            for addon in coordinator.data.values()
        ]
    )


class HassioAddonUpdateAvailableEntity(HassioAddonEntity, BinarySensorEntity):
    """Binary sensor to track whether an update is available for a Hass.io add-on."""

    def __init__(
        self, coordinator: HassioAddonsDataUpdateCoordinator, addon: Dict[str, Any]
    ) -> None:
        """Initialize binary sensor."""
        super().__init__(coordinator, addon, "Update Available")

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.addon_info[ATTR_UPDATE_AVAILABLE]
