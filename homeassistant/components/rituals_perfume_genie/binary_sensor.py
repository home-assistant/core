"""Support for Rituals Perfume Genie binary sensors."""
from __future__ import annotations

from pyrituals import Diffuser

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RitualsDataUpdateCoordinator
from .const import COORDINATORS, DEVICES, DOMAIN
from .entity import DiffuserEntity

CHARGING_SUFFIX = " Battery Charging"
BATTERY_CHARGING_ID = 21


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diffuser binary sensors."""
    diffusers = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities = []
    for hublot, diffuser in diffusers.items():
        if diffuser.has_battery:
            coordinator = coordinators[hublot]
            entities.append(DiffuserBatteryChargingBinarySensor(diffuser, coordinator))

    async_add_entities(entities)


class DiffuserBatteryChargingBinarySensor(DiffuserEntity, BinarySensorEntity):
    """Representation of a diffuser battery charging binary sensor."""

    def __init__(
        self, diffuser: Diffuser, coordinator: RitualsDataUpdateCoordinator
    ) -> None:
        """Initialize the battery charging binary sensor."""
        super().__init__(diffuser, coordinator, CHARGING_SUFFIX)

    @property
    def is_on(self) -> bool:
        """Return the state of the battery charging binary sensor."""
        return self._diffuser.charging

    @property
    def device_class(self) -> str:
        """Return the device class of the battery charging binary sensor."""
        return DEVICE_CLASS_BATTERY_CHARGING
