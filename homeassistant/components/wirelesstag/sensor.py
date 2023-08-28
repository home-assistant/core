"""Sensor support for Wireless Sensor Tags platform."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN as WIRELESSTAG_DOMAIN, SIGNAL_TAG_UPDATE, WirelessTagBaseSensor

_LOGGER = logging.getLogger(__name__)

SENSOR_TEMPERATURE = "temperature"
SENSOR_AMBIENT_TEMPERATURE = "ambient_temperature"
SENSOR_HUMIDITY = "humidity"
SENSOR_MOISTURE = "moisture"
SENSOR_LIGHT = "light"

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    SENSOR_TEMPERATURE: SensorEntityDescription(
        key=SENSOR_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_AMBIENT_TEMPERATURE: SensorEntityDescription(
        key=SENSOR_AMBIENT_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_HUMIDITY: SensorEntityDescription(
        key=SENSOR_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_MOISTURE: SensorEntityDescription(
        key=SENSOR_MOISTURE,
        device_class=SensorDeviceClass.MOISTURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_LIGHT: SensorEntityDescription(
        key=SENSOR_LIGHT,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

SENSOR_KEYS: list[str] = list(SENSOR_TYPES)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        )
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    platform = hass.data[WIRELESSTAG_DOMAIN]
    sensors = []
    tags = platform.tags
    for tag in tags.values():
        for key in config[CONF_MONITORED_CONDITIONS]:
            if key not in tag.allowed_sensor_types:
                continue
            description = SENSOR_TYPES[key]
            sensors.append(WirelessTagSensor(platform, tag, description))

    add_entities(sensors, True)


class WirelessTagSensor(WirelessTagBaseSensor, SensorEntity):
    """Representation of a Sensor."""

    entity_description: SensorEntityDescription

    def __init__(self, api, tag, description):
        """Initialize a WirelessTag sensor."""
        super().__init__(api, tag)

        self._sensor_type = description.key
        self.entity_description = description
        self._name = self._tag.name
        self._attr_unique_id = f"{self.tag_id}_{self._sensor_type}"

        # I want to see entity_id as:
        # sensor.wirelesstag_bedroom_temperature
        # and not as sensor.bedroom for temperature and
        # sensor.bedroom_2 for humidity
        self.entity_id = (
            f"sensor.{WIRELESSTAG_DOMAIN}_{self.underscored_name}_{self._sensor_type}"
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TAG_UPDATE.format(self.tag_id, self.tag_manager_mac),
                self._update_tag_info_callback,
            )
        )

    @property
    def underscored_name(self):
        """Provide name savvy to be used in entity_id name of self."""
        return self.name.lower().replace(" ", "_")

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._sensor.unit

    @property
    def principal_value(self):
        """Return sensor current value."""
        return self._sensor.value

    @property
    def _sensor(self):
        """Return tag sensor entity."""
        return self._tag.sensor[self._sensor_type]

    @callback
    def _update_tag_info_callback(self, new_tag):
        """Handle push notification sent by tag manager."""
        _LOGGER.debug("Entity to update state: %s with new tag: %s", self, new_tag)
        self._tag = new_tag
        self._state = self.updated_state_value()
        self.async_write_ha_state()
