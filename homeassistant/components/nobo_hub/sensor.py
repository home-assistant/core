"""Python Control of Nobø Hub - Nobø Energy Control."""

from typing import override

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
    hub = config_entry.runtime_data

    known_components: set[str] = set()

    @callback
    def _add_sensors(_hub: nobo) -> None:
        """Add temperature sensors for components added to the hub."""
        if hub.connected:
            # Forget components no longer on the hub so a removed-then-re-added
            # component is detected as new again. Skip while disconnected: a
            # stale/empty snapshot would drop live components and cause
            # duplicate re-adds on reconnect.
            known_components.intersection_update(hub.components)
        new_components = [
            serial
            for serial, component in hub.components.items()
            if component[ATTR_MODEL].has_temp_sensor and serial not in known_components
        ]
        known_components.update(new_components)
        async_add_entities(
            NoboTemperatureSensor(serial, hub) for serial in new_components
        )

    _add_sensors(hub)
    hub.register_callback(_add_sensors)
    config_entry.async_on_unload(lambda: hub.deregister_callback(_add_sensors))


class NoboTemperatureSensor(NoboBaseEntity, SensorEntity):
    """A Nobø device with a temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

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

    @property
    @override
    def available(self) -> bool:
        """Available when the hub is connected and the component still exists."""
        return super().available and self._id in self._nobo.components

    @callback
    @override
    def _read_state(self) -> None:
        """Read the current state from the hub. This is a local call."""
        if not self.available:
            return
        value = self._nobo.get_current_component_temperature(self._id)
        self._attr_native_value = None if value is None else float(value)
