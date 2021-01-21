"""Support for SUPLA MQTT sensors."""
from datetime import timedelta
import logging
import queue

import paho.mqtt.client as supla_mqtt

from homeassistant.components.ais_dom import ais_global
import homeassistant.components.mqtt as hass_mqtt
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=1)


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
        self._password = mqtt_settings["password"]
        self._hostname = mqtt_settings["host"]
        self._port = mqtt_settings["port"]
        self._tls = mqtt_settings["tls"]
        self._protocol = mqtt_settings["protocol"]
        self._keepalive = 600
        self._qos = 0
        self._manufacturer = "SUPLA.ORG"
        self._model = "MQTT Bridge"
        self._os_version = "v1"
        self._supla_published = 0
        self._supla_received = 0
        self._supla_mqtt_connection_code = None
        self._supla_mqtt_client = None
        self._sub_state = None

    async def async_publish_to_supla(self, topic, payload):
        if self._supla_mqtt_client is not None:
            self._supla_mqtt_client.publish(
                topic, payload=payload, qos=self._qos, retain=False
            )

    @callback
    async def hass_message_received(self, msg):
        """Handle new MQTT messages."""
        _LOGGER.debug(f"message_received {msg.payload} {msg.topic}")
        payload = msg.payload
        if type(payload) is bytes:
            payload = msg.payload.decode("utf-8")
        await self.async_publish_to_supla(msg.topic, payload)

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
        if self._supla_mqtt_connection_code == 0:
            return "success"
        elif self._supla_mqtt_connection_code == 1:
            return "bad protocol"
        elif self._supla_mqtt_connection_code == 2:
            return "client-id error"
        elif self._supla_mqtt_connection_code == 3:
            return "service unavailable"
        elif self._supla_mqtt_connection_code == 4:
            return "bad username or password"
        return self._supla_mqtt_connection_code

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
            "Host": self._hostname,
            "Port": self._port,
            "Username": self._username,
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:bridge"

    def on_supla_connect(self, client_, userdata, flags, result_code):
        """Handle connection result."""
        _LOGGER.debug(f"on_supla_connect {result_code}")
        self._supla_mqtt_connection_code = result_code
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client_.subscribe("supla/#")
        client_.subscribe("homeassistant/#")

    def on_supla_disconnect(self, client_, userdata, result_code):
        """Handle connection result."""
        _LOGGER.debug(f"on_supla_disconnect {result_code}")
        self._supla_mqtt_connection_code = result_code
        self._supla_mqtt_client = None

    # The callback for when a message is received from SUPLA broker.
    def on_supla_message(self, client, userdata, msg):
        _LOGGER.debug(f"on_message {msg.topic} / {msg.payload}")
        payload = msg.payload.decode("utf-8")
        hass_mqtt.async_publish(self.hass, msg.topic, payload)
        self._supla_received = self._supla_received + 1

    # The callback for when a message is published to SUPLA broker.
    def on_supla_publish(self, client, userdata, mid):
        _LOGGER.debug(f"on_supla_publish {mid}")
        self._supla_published = self._supla_published + 1

    async def async_update(self):
        """Update the sensor."""
        if self._supla_mqtt_client is None:
            client_id = ais_global.get_sercure_android_id_dom()
            self._supla_mqtt_client = supla_mqtt.Client(client_id)
            self._supla_mqtt_client.username_pw_set(
                self._username, password=self._password
            )
            self._supla_mqtt_client.tls_set()
            self._supla_mqtt_client.tls_insecure_set(True)
            result = queue.Queue(maxsize=1)

            self._supla_mqtt_client.on_connect = self.on_supla_connect
            self._supla_mqtt_client.on_disconnect = self.on_supla_disconnect
            self._supla_mqtt_client.on_message = self.on_supla_message
            self._supla_mqtt_client.on_publish = self.on_supla_publish

            self._supla_mqtt_client.connect_async(
                self._hostname, port=self._port, keepalive=self._keepalive
            )
            self._supla_mqtt_client.loop_start()

            try:
                return result.get(timeout=5)
            except queue.Empty:
                pass
