"""Binary sensor support for Wireless Sensor Tags."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    DOMAIN as WIRELESSTAG_DOMAIN,
    SIGNAL_BINARY_EVENT_UPDATE,
    WirelessTagBaseSensor,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Wirelesstags binary sensors."""
    platform = hass.data[WIRELESSTAG_DOMAIN]
    sensors = []
    tags = platform.tags
    for tag in tags.values():
        for sensor_type in tag.supported_binary_events_types:
            sensor = WirelessTagBinarySensor(platform, tag, sensor_type)
            sensors.append(sensor)
    async_add_entities(sensors)


class WirelessTagBinarySensor(WirelessTagBaseSensor, BinarySensorEntity):
    """A binary sensor implementation for Wirelesstags."""

    def __init__(self, api, tag, sensor_type):
        """Initialize a binary sensor for a Wireless Sensor Tags."""
        super().__init__(api, tag)
        self._sensor_type = sensor_type
        self._name = f"{self._tag.name} {self.event.human_readable_name}"
        self.entity_id = f"binary_sensor.{WIRELESSTAG_DOMAIN}_{self.underscored_name}"
        self._state = self.updated_state_value()

    async def async_added_to_hass(self):
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
    def unique_id(self):
        """Return a unique, unchanging string that represents this sensor."""
        return f"{self._tag.uuid}_binary_{self._sensor_type}"

    @property
    def underscored_name(self):
        """Provide name savvy to be used in entity_id name of self."""
        return self.name.lower().replace(" ", "_")

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state == STATE_ON

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._sensor_type

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
    def _on_binary_event_callback(self, new_tag):
        """Update state from arrived push notification."""
        self._tag = new_tag
        self._state = self.updated_state_value()
        self.async_write_ha_state()
