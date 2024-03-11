"""Sensor platform for Advantage Air integration."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ADVANTAGE_AIR_STATE_OPEN, DOMAIN as ADVANTAGE_AIR_DOMAIN
from .entity import AdvantageAirAcEntity, AdvantageAirZoneEntity
from .models import AdvantageAirData

ADVANTAGE_AIR_SET_COUNTDOWN_VALUE = "minutes"
ADVANTAGE_AIR_SET_COUNTDOWN_UNIT = "min"
ADVANTAGE_AIR_SERVICE_SET_TIME_TO = "set_time_to"

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir sensor platform."""

    instance: AdvantageAirData = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities: list[SensorEntity] = []
    if aircons := instance.coordinator.data.get("aircons"):
        for ac_key, ac_device in aircons.items():
            entities.append(AdvantageAirTimeTo(instance, ac_key, "On"))
            entities.append(AdvantageAirTimeTo(instance, ac_key, "Off"))
            for zone_key, zone in ac_device["zones"].items():
                # Only show damper and temp sensors when zone is in temperature control
                if zone["type"] != 0:
                    entities.append(AdvantageAirZoneVent(instance, ac_key, zone_key))
                    entities.append(AdvantageAirZoneTemp(instance, ac_key, zone_key))
                # Only show wireless signal strength sensors when using wireless sensors
                if zone["rssi"] > 0:
                    entities.append(AdvantageAirZoneSignal(instance, ac_key, zone_key))
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
        {vol.Required("minutes"): cv.positive_int},
        "set_time_to",
    )


class AdvantageAirTimeTo(AdvantageAirAcEntity, SensorEntity):
    """Representation of Advantage Air timer control."""

    _attr_native_unit_of_measurement = ADVANTAGE_AIR_SET_COUNTDOWN_UNIT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, instance: AdvantageAirData, ac_key: str, action: str) -> None:
        """Initialize the Advantage Air timer control."""
        super().__init__(instance, ac_key)
        self.action = action
        self._time_key = f"countDownTo{action}"
        self._attr_name = f"Time to {action}"
        self._attr_unique_id += f"-timeto{action}"

    @property
    def native_value(self) -> Decimal:
        """Return the current value."""
        return self._ac[self._time_key]

    @property
    def icon(self) -> str:
        """Return a representative icon of the timer."""
        if self._ac[self._time_key] > 0:
            return "mdi:timer-outline"
        return "mdi:timer-off-outline"

    async def set_time_to(self, **kwargs: Any) -> None:
        """Set the timer value."""
        value = min(720, max(0, int(kwargs[ADVANTAGE_AIR_SET_COUNTDOWN_VALUE])))
        await self.async_update_ac({self._time_key: value})


class AdvantageAirZoneVent(AdvantageAirZoneEntity, SensorEntity):
    """Representation of Advantage Air Zone Vent Sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, instance: AdvantageAirData, ac_key: str, zone_key: str) -> None:
        """Initialize an Advantage Air Zone Vent Sensor."""
        super().__init__(instance, ac_key, zone_key=zone_key)
        self._attr_name = f'{self._zone["name"]} vent'
        self._attr_unique_id += "-vent"

    @property
    def native_value(self) -> Decimal:
        """Return the current value of the air vent."""
        if self._zone["state"] == ADVANTAGE_AIR_STATE_OPEN:
            return self._zone["value"]
        return Decimal(0)

    @property
    def icon(self) -> str:
        """Return a representative icon."""
        if self._zone["state"] == ADVANTAGE_AIR_STATE_OPEN:
            return "mdi:fan"
        return "mdi:fan-off"


class AdvantageAirZoneSignal(AdvantageAirZoneEntity, SensorEntity):
    """Representation of Advantage Air Zone wireless signal sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, instance: AdvantageAirData, ac_key: str, zone_key: str) -> None:
        """Initialize an Advantage Air Zone wireless signal sensor."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = f'{self._zone["name"]} signal'
        self._attr_unique_id += "-signal"

    @property
    def native_value(self) -> Decimal:
        """Return the current value of the wireless signal."""
        return self._zone["rssi"]

    @property
    def icon(self) -> str:
        """Return a representative icon."""
        if self._zone["rssi"] >= 80:
            return "mdi:wifi-strength-4"
        if self._zone["rssi"] >= 60:
            return "mdi:wifi-strength-3"
        if self._zone["rssi"] >= 40:
            return "mdi:wifi-strength-2"
        if self._zone["rssi"] >= 20:
            return "mdi:wifi-strength-1"
        return "mdi:wifi-strength-outline"


class AdvantageAirZoneTemp(AdvantageAirZoneEntity, SensorEntity):
    """Representation of Advantage Air Zone temperature sensor."""

    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, instance: AdvantageAirData, ac_key: str, zone_key: str) -> None:
        """Initialize an Advantage Air Zone Temp Sensor."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = f'{self._zone["name"]} temperature'
        self._attr_unique_id += "-temp"

    @property
    def native_value(self) -> Decimal:
        """Return the current value of the measured temperature."""
        return self._zone["measuredTemp"]
