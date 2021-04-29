"""Sensor platform for Hass.io addons."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ADDONS_COORDINATOR
from .const import ATTR_VERSION, ATTR_VERSION_LATEST
from .entity import HassioAddonEntity, HassioOSEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensor set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    entities = []

    for attribute_name, sensor_name in (
        (ATTR_VERSION, "Version"),
        (ATTR_VERSION_LATEST, "Newest Version"),
    ):
        for addon in coordinator.data["addons"].values():
            entities.append(
                HassioAddonSensor(coordinator, addon, attribute_name, sensor_name)
            )
        if coordinator.is_hass_os:
            entities.append(HassioOSSensor(coordinator, attribute_name, sensor_name))

    async_add_entities(entities)


class HassioAddonSensor(HassioAddonEntity, SensorEntity):
    """Sensor to track a Hass.io add-on attribute."""

    @property
    def state(self) -> str:
        """Return state of entity."""
        return self.addon_info[self.attribute_name]


class HassioOSSensor(HassioOSEntity, SensorEntity):
    """Sensor to track a Hass.io add-on attribute."""

    @property
    def state(self) -> str:
        """Return state of entity."""
        return self.os_info[self.attribute_name]
