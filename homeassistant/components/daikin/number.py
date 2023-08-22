"""Support for Daikin AirBase zone temperatures."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
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
    _registry: er.EntityRegistry | None
    _remove_listener: Callable[[], None] | None
    _target_temperature: float
    _previous_value: float | None
    _current_value: float

    def __init__(self, daikin_api: DaikinApi, zone_id) -> None:
        """Initialize the zone."""
        self._api = daikin_api
        self._zone_id = zone_id
        self._registry = None
        self._remove_listener = None
        self._target_temperature = self._api.device.target_temperature
        self._previous_value = None
        self._current_value = self._api.device.zones[self._zone_id][2]
        self._attr_device_info = self._api.device_info
        self._attr_unique_id = f"{self._api.device.mac}-zone-temp{self._zone_id}"
        self._attr_name = f"{self._api.device.zones[self._zone_id][0]} temperature"
        self._attr_native_min_value = self._target_temperature - 2
        self._attr_native_max_value = self._target_temperature + 2

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        if self.has_updated_value():
            self._previous_value = None
            self._current_value = self._api.device.zones[self._zone_id][2]
        return self._current_value

    def has_updated_value(self) -> bool:
        """Detect if api has an updated value."""
        if self._previous_value == self._api.device.zones[self._zone_id][2]:
            return False
        if self.value_in_range(self._api.device.zones[self._zone_id][2]):
            return True
        return False

    def value_in_range(self, value: float) -> bool:
        """Check temperature is within range."""
        if value < (self._target_temperature - 2) or value > (
            self._target_temperature + 2
        ):
            return False
        return True

    async def async_added_to_hass(self) -> None:
        """Add listener when entity about to be added to hass."""
        registry = self.async_get_registry()
        entity_id = registry.async_get_entity_id(
            Platform.CLIMATE, DAIKIN_DOMAIN, self._api.device.mac
        )

        if entity_id is not None:
            self._remove_listener = async_track_state_change_event(
                self.hass, entity_id, self.async_update_value
            )

    async def async_will_remove_from_hass(self) -> None:
        """Remove listener when entity about to be removed to hass."""
        if self._remove_listener is not None:
            self._remove_listener()

    @callback
    def async_update_value(self, event: Event) -> None:
        """Update zone state."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return None

        if (new_temp := new_state.attributes.get(ATTR_TEMPERATURE)) is None:
            return None

        self._target_temperature = new_temp

        if not self.value_in_range(self._current_value):
            self._previous_value = self._current_value

            if self._current_value < (new_temp - 2):
                self._current_value = new_temp - 2
            elif self._current_value > (new_temp + 2):
                self._current_value = new_temp + 2

        self.async_write_ha_state()

    @callback
    def async_get_registry(self) -> er.EntityRegistry:
        """Get or return Entity Registry."""
        if self._registry is None:
            self._registry = er.async_get(self.hass)
        return self._registry

    async def async_update(self) -> None:
        """Retrieve latest state."""
        await self._api.async_update()

    async def async_set_native_value(self, value: float) -> None:
        """Set the zone temperature."""
        if not self.value_in_range(value):
            return None
        self._current_value = value
        await self._api.device.set_zone(
            self._zone_id, "lztemp_h", str(round(self._current_value))
        )
