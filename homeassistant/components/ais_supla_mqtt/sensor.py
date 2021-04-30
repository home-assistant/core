"""Support for SUPLA MQTT sensors."""
from datetime import timedelta
import logging

import homeassistant.components.mqtt as hass_mqtt
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=2)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for SUPLA MQTT status sensor."""
    _LOGGER.debug("SUPLA MQTT sensor, async_setup_entry")
    config_mqtt_settings = hass.data[DOMAIN][config_entry.entry_id]
    mqtt_settings = config_mqtt_settings.data
    async_add_entities([SuplaMqttSoftBridge(hass, mqtt_settings)], True)


class SuplaMqttSoftBridge(Entity):
    """Supla Mqtt Soft Bridge representation."""

    def __init__(self, hass, mqtt_settings):
        """Sensor initialization."""
        self._username = mqtt_settings["username"]
        self._qos = 0
        self._manufacturer = "SUPLA.ORG"
        self._model = "MQTT Bridge"
        self._os_version = "v2"
        self._supla_published = 0
        self._supla_received = 0
        self._sub_state = None

    @callback
    async def hass_message_received(self, msg):
        """Handle new MQTT messages."""
        self._supla_received = self._supla_published + 1

    @callback
    async def supla_message_received(self, msg):
        """Handle new MQTT messages."""
        self._supla_received = self._supla_received + 1

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await self._subscribe_topics()

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

        self._sub_state = await hass_mqtt.subscription.async_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                "execute": {
                    "topic": "supla/+/devices/+/channels/+/execute_action",
                    "msg_callback": self.hass_message_received,
                    "qos": self._qos,
                },
                "set": {
                    "topic": "supla/+/devices/+/channels/+/set/+",
                    "msg_callback": self.hass_message_received,
                    "qos": self._qos,
                },
                "set": {
                    "topic": "supla/#",
                    "msg_callback": self.supla_message_received,
                    "qos": self._qos,
                },
                "set": {
                    "topic": "homeassistant/#",
                    "msg_callback": self.supla_message_received,
                    "qos": self._qos,
                },
            },
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await hass_mqtt.subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {(DOMAIN, self._username)},
            "name": f"MQTT Bridge",
            "manufacturer": self._manufacturer,
            "model": self._model,
            "sw_version": self._os_version,
            "via_device": None,
        }

    @property
    def unique_id(self) -> str:
        """Return a unique, friendly identifier for this entity."""
        return self._username

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"SUPLA connection status"

    @property
    def state(self):
        """Return the status of the sensor."""
        # connection result codes
        return "mqtt bridge connection"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return ""

    @property
    def device_state_attributes(self):
        """Return the attributes of the device."""
        return {
            "MQTT packets sent": self._supla_published,
            "MQTT packets received": self._supla_received,
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:bridge"

    async def async_update(self):
        """Sensor update."""
        pass
