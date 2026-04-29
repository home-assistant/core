"""Python Control of Nobø Hub - Nobø Energy Control."""

from __future__ import annotations

from pynobo import nobo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import ATTR_MODEL, ATTR_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import NoboHubConfigEntry
from .const import ATTR_SERIAL, ATTR_ZONE_ID, DOMAIN, NOBO_MANUFACTURER
from .entity import NoboBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NoboHubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up any temperature sensors connected to the Nobø Ecohub."""

    # Setup connection with hub
    hub = config_entry.runtime_data

    async_add_entities(
        NoboTemperatureSensor(component["serial"], hub)
        for component in hub.components.values()
        if component[ATTR_MODEL].has_temp_sensor
    )


class NoboTemperatureSensor(NoboBaseEntity, SensorEntity):
    """A Nobø device with a temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, serial: str, hub: nobo) -> None:
        """Initialize the temperature sensor."""
        super().__init__(hub)
        self._temperature: StateType = None
        self._id = serial
        component = hub.components[self._id]
        self._attr_unique_id = component[ATTR_SERIAL]
        zone_id = component[ATTR_ZONE_ID]
        suggested_area = None
        if zone_id != "-1":
            suggested_area = hub.zones[zone_id][ATTR_NAME]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, component[ATTR_SERIAL])},
            serial_number=component[ATTR_SERIAL],
            name=component[ATTR_NAME],
            manufacturer=NOBO_MANUFACTURER,
            model=component[ATTR_MODEL].name,
            via_device=(DOMAIN, hub.hub_info[ATTR_SERIAL]),
            suggested_area=suggested_area,
        )
        self._read_state()

    @callback
    def _read_state(self) -> None:
        """Read the current state from the hub. This is a local call."""
        if self._id not in self._nobo.components:
            # Component removed via the Nobø app; mark unavailable.
            self._attr_available = False
            return
        self._attr_available = True
        value = self._nobo.get_current_component_temperature(self._id)
        if value is None:
            self._attr_native_value = None
        else:
            self._attr_native_value = round(float(value), 1)
