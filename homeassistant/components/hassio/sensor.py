"""Sensor platform for Hass.io addons."""
from typing import Callable, List

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from . import ADDONS_COORDINATOR
from .const import ATTR_VERSION, ATTR_VERSION_LATEST
from .entity import HassioAddonEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Sensor set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    entities = []

    for addon in coordinator.data.values():
        for name, attribute in (
            (ATTR_VERSION, "Current Version"),
            (ATTR_VERSION_LATEST, "Latest Version"),
        ):
            entities.append(HassioAddonSensor(coordinator, addon, name, attribute))

    async_add_entities(entities)


class HassioAddonSensor(HassioAddonEntity):
    """Sensor to track a Hass.io add-on attribute."""

    @property
    def state(self) -> str:
        """Return state of entity."""
        return self.addon_info[self.attribute_name]
