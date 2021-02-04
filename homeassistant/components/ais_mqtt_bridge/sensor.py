"""Support for MQTT BRIDGE sensors."""
from datetime import timedelta
import logging

import paho.mqtt.client as ais_mqtt

import homeassistant.components.mqtt as hass_mqtt
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=1)


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
        self._username = mqtt_settings["user"]
        self._password = mqtt_settings["token"]
        self._hostname = mqtt_settings["server"]
        self._client_id = mqtt_settings["client"]
        self._port = mqtt_settings["port"]
        self._keepalive = 600
        self._qos = 0
        self._manufacturer = "AI-Speaker.com"
        self._model = "MQTT Bridge"
        self._os_version = "v1"
        self._ais_cloud_published = 0
        self._ais_cloud_received = 0
        self._ais_mqtt_connection_code = -1
        self._sub_state = None
        self._try_to_connect_no = 0

        # connection on start
        self._ais_mqtt_client = ais_mqtt.Client(
            self._client_id, protocol=ais_mqtt.MQTTv5
        )
        self._ais_mqtt_client.username_pw_set(self._username, password=self._password)
        self._ais_mqtt_client.on_connect = self.on_ais_connect
        self._ais_mqtt_client.on_disconnect = self.on_ais_disconnect
        self._ais_mqtt_client.on_message = self.on_ais_message
        self._ais_mqtt_client.on_publish = self.on_ais_publish

        self._ais_mqtt_client.connect_async(
            self._hostname, port=self._port, keepalive=self._keepalive
        )
        self._ais_mqtt_client.loop_start()

    async def async_publish_to_ais(self, topic, payload):
        if self._ais_mqtt_connection_code == 0:
            self._ais_mqtt_client.publish(
                topic=topic, payload=payload, qos=self._qos, retain=False
            )

    @callback
    async def hass_message_received(self, msg):
        """Handle new MQTT messages."""
        payload = msg.payload
        if type(payload) is bytes:
            payload = msg.payload.decode("utf-8")
        self._ais_cloud_published = self._ais_cloud_published + 1
        await self.async_publish_to_ais(msg.topic, payload)

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await self._subscribe_topics()

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

        self._sub_state = await hass_mqtt.subscription.async_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                "ais": {
                    "topic": "ais/#",
                    "msg_callback": self.hass_message_received,
                    "qos": self._qos,
                }
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
        return f"AIS connection status"

    @property
    def state(self):
        """Return the status of the sensor."""
        # connection result codes
        if self._ais_mqtt_connection_code == -1:
            return "starting"
        elif self._ais_mqtt_connection_code == 0:
            return "success"
        elif self._ais_mqtt_connection_code == 1:
            return "bad protocol"
        elif self._ais_mqtt_connection_code == 2:
            return "client-id error"
        elif self._ais_mqtt_connection_code == 3:
            return "service unavailable"
        elif self._ais_mqtt_connection_code == 4:
            return "bad username or password"
        elif self._ais_mqtt_connection_code == 5:
            return "not authorised"
        return self._ais_mqtt_connection_code

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return ""

    @property
    def device_state_attributes(self):
        """Return the attributes of the device."""
        return {
            "MQTT packets sent": self._ais_cloud_published,
            "MQTT packets received": self._ais_cloud_received,
            "MQTT trying to connect": self._try_to_connect_no,
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:bridge"

    def on_ais_connect(self, client_, userdata, flags, result_code, properties):
        """Handle connection result.
        Subscribing in on_connect() means that if we lose the connection and
        reconnect then subscriptions will be renewed."""
        self._try_to_connect_no = self._try_to_connect_no + 1
        self._ais_mqtt_connection_code = result_code
        if result_code == 0:
            client_.subscribe("dom/#")

    def on_ais_disconnect(self, client_, userdata, result_code):
        """Handle connection result."""
        self._ais_mqtt_connection_code = result_code

    def on_ais_message(self, client, userdata, msg):
        """The callback for when a PUBLISH message is received from ais cloud broker."""
        payload = msg.payload.decode("utf-8")
        self._ais_cloud_received = self._ais_cloud_received + 1
        hass_mqtt.async_publish(self.hass, msg.topic, payload)

    def on_ais_publish(self, client, userdata, mid):
        """The callback for when a message is published to ais cloud broker."""
        _LOGGER.debug(f"on_ais_publish {mid}")
        self._ais_cloud_published = self._ais_cloud_published + 1

    async def async_update(self):
        """Update the sensor."""
        pass
