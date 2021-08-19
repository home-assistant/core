"""Support for Renault binary sensors."""
from __future__ import annotations

from renault_api.kamereon.enums import ChargeState, PlugState

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_PLUG,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .renault_entities import RenaultBatteryDataEntity, RenaultDataEntity
from .renault_hub import RenaultHub


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    proxy: RenaultHub = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[RenaultDataEntity] = []
    for vehicle in proxy.vehicles.values():
        if "battery" in vehicle.coordinators:
            entities.append(RenaultPluggedInSensor(vehicle, "Plugged In"))
            entities.append(RenaultChargingSensor(vehicle, "Charging"))
    async_add_entities(entities)


class RenaultPluggedInSensor(RenaultBatteryDataEntity, BinarySensorEntity):
    """Plugged In binary sensor."""

    _attr_device_class = DEVICE_CLASS_PLUG

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if (not self.data) or (self.data.plugStatus is None):
            return None
        return self.data.get_plug_status() == PlugState.PLUGGED


class RenaultChargingSensor(RenaultBatteryDataEntity, BinarySensorEntity):
    """Charging binary sensor."""

    _attr_device_class = DEVICE_CLASS_BATTERY_CHARGING

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if (not self.data) or (self.data.chargingStatus is None):
            return None
        return self.data.get_charging_status() == ChargeState.CHARGE_IN_PROGRESS
