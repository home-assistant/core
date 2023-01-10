"""Python Control of Nobø Hub - Nobø Energy Control."""
from __future__ import annotations

from pynobo import nobo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SUGGESTED_AREA,
    ATTR_VIA_DEVICE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import ATTR_SERIAL, ATTR_ZONE_ID, DOMAIN, NOBO_MANUFACTURER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up any temperature sensors connected to the Nobø Ecohub."""

    # Setup connection with hub
    hub: nobo = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        NoboTemperatureSensor(component["serial"], hub)
        for component in hub.components.values()
        if component[ATTR_MODEL].has_temp_sensor
    )


class NoboTemperatureSensor(SensorEntity):
    """A Nobø device with a temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False

    def __init__(self, serial: str, hub: nobo) -> None:
        """Initialize the temperature sensor."""
        self._temperature: StateType = None
        self._id = serial
        self._nobo = hub
        component = hub.components[self._id]
        self._attr_unique_id = component[ATTR_SERIAL]
        self._attr_name = "Temperature"
        self._attr_has_entity_name = True
        self._attr_device_info: DeviceInfo = {
            ATTR_IDENTIFIERS: {(DOMAIN, component[ATTR_SERIAL])},
            ATTR_NAME: component[ATTR_NAME],
            ATTR_MANUFACTURER: NOBO_MANUFACTURER,
            ATTR_MODEL: component[ATTR_MODEL].name,
            ATTR_VIA_DEVICE: (DOMAIN, hub.hub_info[ATTR_SERIAL]),
        }
        zone_id = component[ATTR_ZONE_ID]
        if zone_id != "-1":
            self._attr_device_info[ATTR_SUGGESTED_AREA] = hub.zones[zone_id][ATTR_NAME]
        self._read_state()

    async def async_added_to_hass(self) -> None:
        """Register callback from hub."""
        self._nobo.register_callback(self._after_update)

    async def async_will_remove_from_hass(self) -> None:
        """Deregister callback from hub."""
        self._nobo.deregister_callback(self._after_update)

    @callback
    def _read_state(self) -> None:
        """Read the current state from the hub. This is a local call."""
        value = self._nobo.get_current_component_temperature(self._id)
        if value is None:
            self._attr_native_value = None
        else:
            self._attr_native_value = round(float(value), 1)

    @callback
    def _after_update(self, hub) -> None:
        self._read_state()
        self.async_write_ha_state()
