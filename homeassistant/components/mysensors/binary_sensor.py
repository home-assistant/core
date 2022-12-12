"""Support for MySensors binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .. import mysensors
from .const import MYSENSORS_DISCOVERY, DiscoveryInfo
from .helpers import on_unload

SENSORS = {
    "S_DOOR": BinarySensorDeviceClass.DOOR,
    "S_MOTION": BinarySensorDeviceClass.MOTION,
    "S_SMOKE": BinarySensorDeviceClass.SMOKE,
    "S_SPRINKLER": BinarySensorDeviceClass.SAFETY,
    "S_WATER_LEAK": BinarySensorDeviceClass.SAFETY,
    "S_SOUND": BinarySensorDeviceClass.SOUND,
    "S_VIBRATION": BinarySensorDeviceClass.VIBRATION,
    "S_MOISTURE": BinarySensorDeviceClass.MOISTURE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""

    @callback
    def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors binary_sensor."""
        mysensors.setup_mysensors_platform(
            hass,
            Platform.BINARY_SENSOR,
            discovery_info,
            MySensorsBinarySensor,
            async_add_entities=async_add_entities,
        )

    on_unload(
        hass,
        config_entry.entry_id,
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, Platform.BINARY_SENSOR),
            async_discover,
        ),
    )


class MySensorsBinarySensor(mysensors.device.MySensorsEntity, BinarySensorEntity):
    """Representation of a MySensors Binary Sensor child node."""

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self._values.get(self.value_type) == STATE_ON

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the class of this sensor, from DEVICE_CLASSES."""
        pres = self.gateway.const.Presentation
        return SENSORS.get(pres(self.child_type).name)
