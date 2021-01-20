"""Support for MQTT BRIDGE sensors."""
from datetime import timedelta
import logging
import queue

import paho.mqtt.client as mqtt

from homeassistant.components.ais_dom import ais_global
from homeassistant.components.mqtt import subscription
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for AIS MQTT BRIDGE status sensor."""
    _LOGGER.debug("AIS MQTT BRIDGE sensor, async_setup_entry")
    config_mqtt_settings = hass.data[DOMAIN][config_entry.entry_id]
    mqtt_settings = config_mqtt_settings.data
    async_add_entities([AisMqttSoftBridge(hass, mqtt_settings)], True)


class AisMqttSoftBridge(Entity):
    """AIS Mqtt Soft Bridge representation."""

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
        self._manufacturer = "AI-Speaker.com"
        self._model = "MQTT Bridge"
        self._os_version = "v1"
        self._ais_mqtt_connection_code = None
        self._ais_mqtt_client = None
        self._sub_state = None

    @callback
    def hass_message_received(self, msg):
        """Handle new MQTT messages."""
        _LOGGER.degug(f"message_received {msg.payload} {msg.topic}")
        if self._ais_mqtt_client is not None:
            self._ais_mqtt_client.publish(
                msg.topic, payload=msg.payload, qos=self._qos, retain=False
            )

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await self._subscribe_topics()

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                "execute": {
                    "topic": "ais/+/devices/+/channels/+/execute_action",
                    "msg_callback": self.hass_message_received,
                    "qos": self._qos,
                },
                "set": {
                    "topic": "ais/+/devices/+/channels/+/set/+",
                    "msg_callback": self.hass_message_received,
                    "qos": self._qos,
                },
            },
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await subscription.async_unsubscribe_topics(
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
        return f"Connection status"

    @property
    def state(self):
        """Return the status of the sensor."""
        return self._ais_mqtt_connection_code

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return ""

    @property
    def device_state_attributes(self):
        """Return the attributes of the device."""
        return {
            "username": self._username,
            "password": self._password,
            "tls": self._tls,
            "host": self._hostname,
            "port": self._port,
            "protocol": self._protocol,
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:bridge"

    def on_ais_connect(self, client_, userdata, flags, result_code):
        """Handle connection result."""
        _LOGGER.debug(f"on_ais_connect {result_code}")
        self._ais_mqtt_connection_code = result_code
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client_.subscribe("ais/#")
        client_.subscribe("homeassistant/#")

    def on_ais_disconnect(self, client_, userdata, result_code):
        """Handle connection result."""
        _LOGGER.debug(f"on_ais_disconnect {result_code}")
        self._ais_mqtt_connection_code = result_code
        self._ais_mqtt_client = None

    # The callback for when a PUBLISH message is received from ais broker.
    def on_ais_message(self, client, userdata, msg):
        _LOGGER.debug(f"on_message {msg.topic} / {msg.payload}")
        self.hass.services.call(
            "mqtt", "publish", {"topic": msg.topic, "payload": msg.payload}
        )

    async def async_update(self):
        """Update the sensor."""
        if self._ais_mqtt_client is None:
            client_id = ais_global.get_sercure_android_id_dom()
            self._ais_mqtt_client = mqtt.Client(client_id)
            self._ais_mqtt_client.username_pw_set(
                self._username, password=self._password
            )
            self._ais_mqtt_client.tls_set()
            self._ais_mqtt_client.tls_insecure_set(True)
            # connection result codes
            # 0 - success, connection accepted
            # 1 - connection refused, bad protocol
            # 2 - refused, client-id error
            # 3 - refused, service unavailable
            # 4 - refused, bad username or password
            result = queue.Queue(maxsize=1)

            def on_ais_publish(client, userdata, mid):
                _LOGGER.debug(f"on_ais_publish {mid}")

            self._ais_mqtt_client.on_connect = self.on_ais_connect
            self._ais_mqtt_client.on_disconnect = self.on_ais_disconnect
            self._ais_mqtt_client.on_message = self.on_ais_message
            self._ais_mqtt_client.on_publish = on_ais_publish

            self._ais_mqtt_client.connect_async(
                self._hostname, port=self._port, keepalive=self._keepalive
            )
            self._ais_mqtt_client.loop_start()

            try:
                return result.get(timeout=5)
            except queue.Empty:
                pass
