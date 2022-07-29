"""Support for Satel Integra zone states- represented as binary sensors."""
from __future__ import annotations

from satel_integra.satel_integra import AsyncSatel

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_OUTPUTS,
    CONF_ZONE_NAME,
    CONF_ZONE_TYPE,
    CONF_ZONES,
    DATA_SATEL_CONFIG,
    DOMAIN,
    SIGNAL_OUTPUTS_UPDATED,
    SIGNAL_ZONES_UPDATED,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Satel binary sensor platform."""
    controller: AsyncSatel = hass.data[DOMAIN]
    config: ConfigType = hass.data[DATA_SATEL_CONFIG]

    configured_zones = config[CONF_ZONES]
    configured_outputs = config[CONF_OUTPUTS]

    devices = []

    for zone_num, device_config_data in configured_zones.items():
        zone_type = device_config_data[CONF_ZONE_TYPE]
        zone_name = device_config_data[CONF_ZONE_NAME]
        device = SatelIntegraBinarySensor(
            controller, zone_num, zone_name, zone_type, SIGNAL_ZONES_UPDATED
        )
        devices.append(device)

    for zone_num, device_config_data in configured_outputs.items():
        zone_type = device_config_data[CONF_ZONE_TYPE]
        zone_name = device_config_data[CONF_ZONE_NAME]
        device = SatelIntegraBinarySensor(
            controller, zone_num, zone_name, zone_type, SIGNAL_OUTPUTS_UPDATED
        )
        devices.append(device)

    async_add_entities(devices)


class SatelIntegraBinarySensor(BinarySensorEntity):
    """Representation of an Satel Integra binary sensor."""

    def __init__(
        self, controller, device_number, device_name, zone_type, react_to_signal
    ):
        """Initialize the binary_sensor."""
        self._device_number = device_number
        self._name = device_name
        self._zone_type = zone_type
        self._state = 0
        self._react_to_signal = react_to_signal
        self._satel = controller

    async def async_added_to_hass(self):
        """Register callbacks."""
        if self._react_to_signal == SIGNAL_OUTPUTS_UPDATED:
            if self._device_number in self._satel.violated_outputs:
                self._state = 1
            else:
                self._state = 0
        else:
            if self._device_number in self._satel.violated_zones:
                self._state = 1
            else:
                self._state = 0
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._react_to_signal, self._devices_updated
            )
        )

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self):
        """Icon for device by its type."""
        if self._zone_type is BinarySensorDeviceClass.SMOKE:
            return "mdi:fire"

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state == 1

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._zone_type

    @callback
    def _devices_updated(self, zones):
        """Update the zone's state, if needed."""
        if self._device_number in zones and self._state != zones[self._device_number]:
            self._state = zones[self._device_number]
            self.async_write_ha_state()
