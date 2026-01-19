"""Binary sensor support for Wireless Sensor Tags."""

from __future__ import annotations

import voluptuous as vol
from wirelesstagpy import SensorTag, constants as WT_CONSTANTS

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import WirelessTagPlatform
from .const import SIGNAL_BINARY_EVENT_UPDATE, WIRELESSTAG_DATA
from .entity import WirelessTagBaseSensor
from .util import async_migrate_unique_id

# Sensor types: Name, device_class, push notification type representing 'on',
# attr to check
SENSOR_TYPES = {
    WT_CONSTANTS.EVENT_PRESENCE: BinarySensorDeviceClass.PRESENCE,
    WT_CONSTANTS.EVENT_MOTION: BinarySensorDeviceClass.MOTION,
    WT_CONSTANTS.EVENT_DOOR: BinarySensorDeviceClass.DOOR,
    WT_CONSTANTS.EVENT_COLD: BinarySensorDeviceClass.COLD,
    WT_CONSTANTS.EVENT_HEAT: BinarySensorDeviceClass.HEAT,
    WT_CONSTANTS.EVENT_DRY: None,
    WT_CONSTANTS.EVENT_WET: None,
    WT_CONSTANTS.EVENT_LIGHT: BinarySensorDeviceClass.LIGHT,
    WT_CONSTANTS.EVENT_MOISTURE: BinarySensorDeviceClass.MOISTURE,
    WT_CONSTANTS.EVENT_BATTERY: BinarySensorDeviceClass.BATTERY,
}


PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        )
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the platform for a WirelessTags."""
    platform = hass.data[WIRELESSTAG_DATA]

    sensors = []
    tags = platform.tags
    for tag in tags.values():
        allowed_sensor_types = tag.supported_binary_events_types
        for sensor_type in config[CONF_MONITORED_CONDITIONS]:
            if sensor_type in allowed_sensor_types:
                async_migrate_unique_id(hass, tag, Platform.BINARY_SENSOR, sensor_type)
                sensors.append(WirelessTagBinarySensor(platform, tag, sensor_type))

    async_add_entities(sensors, True)


class WirelessTagBinarySensor(WirelessTagBaseSensor, BinarySensorEntity):
    """A binary sensor implementation for WirelessTags."""

    def __init__(
        self, api: WirelessTagPlatform, tag: SensorTag, sensor_type: str
    ) -> None:
        """Initialize a binary sensor for a Wireless Sensor Tags."""
        super().__init__(api, tag)
        self._sensor_type = sensor_type
        self._attr_device_class = SENSOR_TYPES[sensor_type]
        self._attr_name = f"{self._tag.name} {self.event.human_readable_name}"
        self._attr_unique_id = f"{self._uuid}_{self._sensor_type}"

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        tag_id = self.tag_id
        event_type = self.device_class
        mac = self.tag_manager_mac
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_BINARY_EVENT_UPDATE.format(tag_id, event_type, mac),
                self._on_binary_event_callback,
            )
        )

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self._state == STATE_ON

    @property
    def event(self):
        """Binary event of tag."""
        return self._tag.event[self._sensor_type]

    @property
    def principal_value(self):
        """Return value of tag.

        Subclasses need override based on type of sensor.
        """
        return STATE_ON if self.event.is_state_on else STATE_OFF

    def updated_state_value(self):
        """Use raw princial value."""
        return self.principal_value

    @callback
    def _on_binary_event_callback(self, new_tag: SensorTag) -> None:
        """Update state from arrived push notification."""
        self._tag = new_tag
        self._state = self.updated_state_value()
        self.async_write_ha_state()
