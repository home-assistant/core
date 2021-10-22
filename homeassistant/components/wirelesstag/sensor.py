"""Sensor support for Wireless Sensor Tags platform."""
import logging

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN as WIRELESSTAG_DOMAIN, SIGNAL_TAG_UPDATE, WirelessTagBaseSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Wirelesstags sensors."""
    platform = hass.data[WIRELESSTAG_DOMAIN]
    sensors = []
    tags = platform.tags
    for tag in tags.values():
        for sensor_type in tag.allowed_sensor_types:
            sensor = WirelessTagSensor(platform, tag, sensor_type, hass.config)
            sensors.append(sensor)
    async_add_entities(sensors)


class WirelessTagSensor(WirelessTagBaseSensor, SensorEntity):
    """Representation of a Sensor."""

    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, api, tag, sensor_type, config):
        """Initialize a WirelessTag sensor."""
        super().__init__(api, tag)

        self._sensor_type = sensor_type
        self._name = self._tag.name

        # I want to see entity_id as:
        # sensor.wirelesstag_bedroom_temperature
        # and not as sensor.bedroom for temperature and
        # sensor.bedroom_2 for humidity
        self.entity_id = (
            f"sensor.{WIRELESSTAG_DOMAIN}_{self.underscored_name}_{self._sensor_type}"
        )
        self._state = self.updated_state_value()

    async def async_added_to_hass(self):
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
    def unique_id(self):
        """Return a unique, unchanging string that represents this sensor."""
        return f"{self._tag.uuid}_{self._sensor_type}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._sensor_type

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
