"""Binary sensor platform for Hass.io addons."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import AddEntitiesCallback

from . import ADDONS_COORDINATOR
from .const import ATTR_UPDATE_AVAILABLE
from .entity import HassioAddonEntity, HassioOSEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Binary sensor set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    entities = [
        HassioAddonBinarySensor(
            coordinator, addon, ATTR_UPDATE_AVAILABLE, "Update Available"
        )
        for addon in coordinator.data["addons"].values()
    ]
    if coordinator.is_hass_os:
        entities.append(
            HassioOSBinarySensor(coordinator, ATTR_UPDATE_AVAILABLE, "Update Available")
        )
    async_add_entities(entities)


class HassioAddonBinarySensor(HassioAddonEntity, BinarySensorEntity):
    """Binary sensor to track whether an update is available for a Hass.io add-on."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.addon_info[self.attribute_name]


class HassioOSBinarySensor(HassioOSEntity, BinarySensorEntity):
    """Binary sensor to track whether an update is available for Hass.io OS."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.os_info[self.attribute_name]
