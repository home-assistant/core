"""Support for Daikin AirBase zone temperatures."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from . import DOMAIN as DAIKIN_DOMAIN, DaikinApi


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Daikin climate based on config_entry."""
    daikin_api: DaikinApi = hass.data[DAIKIN_DOMAIN][entry.entry_id]
    if zones := daikin_api.device.zones:
        async_add_entities(
            [
                DaikinZoneTemperature(daikin_api, zone_id)
                for zone_id, zone in enumerate(zones)
                if zone[0] != "-" and zone[2] != 0
            ]
        )


class DaikinZoneTemperature(NumberEntity):
    """Representation of a zone temperature setting."""

    _attr_icon = "mdi:thermostat"
    _attr_native_step = 1
    _attr_has_entity_name = True
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, daikin_api: DaikinApi, zone_id) -> None:
        """Initialize the zone."""
        self._api = daikin_api
        self._zone_id = zone_id
        self._target_temperature = self._api.device.target_temperature

        # Check if the zone has temperature control
        if len(self._api.device.zones[self._zone_id]) < 3 or self._api.device.zones[self._zone_id][2] == 0:
            raise IndexError("Zone does not have temperature control")

        self._current_value = self._api.device.zones[self._zone_id][2]
        self._attr_device_info = self._api.device_info
        self._attr_unique_id = f"{self._api.device.mac}-zone-temp{self._zone_id}"
        self._attr_name = f"{self._api.device.zones[self._zone_id][0]} temperature"
        self._attr_native_min_value = self._target_temperature - 2
        self._attr_native_max_value = self._target_temperature + 2

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        self._current_value = self._api.device.zones[self._zone_id][2]
        return self._current_value

    async def async_update(self) -> None:
        """Retrieve latest state."""
        await self._api.async_update()
        self._current_value = self._api.device.zones[self._zone_id][2]

    async def async_set_native_value(self, value: float) -> None:
        """Set the zone temperature."""
        if value < self._attr_native_min_value or value > self._attr_native_max_value:
            raise HomeAssistantError("Value out of range")
        self._current_value = value
        await self._api.device.set_zone(
            self._zone_id, "lztemp_h", str(round(self._current_value))
        )
