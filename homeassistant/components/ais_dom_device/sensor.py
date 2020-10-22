"""Support for AIS dom MQTT sensors."""
import json
import logging
from typing import Optional

from homeassistant.components.mqtt import (
    CONF_QOS,
    CONF_STATE_TOPIC,
    CONF_UNIQUE_ID,
    subscription,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
G_RF_CODES = []


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up MQTT sensors through configuration.yaml."""
    config_entry = {
        CONF_NAME: "Ais Dom Mqtt RF Sensor",
        CONF_UNIQUE_ID: "ais_dom_mqtt_rf_sensor",
        CONF_QOS: 0,
        CONF_STATE_TOPIC: "tele/+/RESULT",
    }
    async_add_entities([MqttAisDomSensor(config_entry, "ais_dom_mqtt_sensor")])


class MqttAisDomSensor(Entity):
    """Representation of a sensor that can be updated using MQTT."""

    def __init__(self, config_entry, entity_ids):
        """Initialize the sensor."""
        self._config = config_entry
        self._unique_id = config_entry.get(CONF_UNIQUE_ID)
        self._state = None
        self._sub_state = None
        self._codes = []
        self._device_attributes = None

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await self._subscribe_topics()

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            try:
                payload = json.loads(msg.payload)
                if "RfRaw" in payload:
                    b1_code = payload.get("RfRaw")["Data"]
                    if b1_code == "AAA055":
                        # 'A0' means 'ACK'
                        return
                    topic = msg.topic
                    b0_code = get_b0_from_b1(b1_code)
                    code = {"topic": topic, "B1": b1_code, "B0": b0_code}
                    G_RF_CODES.append(code)
                    self._state = payload
                    self.async_write_ha_state()

            except Exception as e:
                _LOGGER.info("Error: " + str(e))

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                "state_topic": {
                    "topic": self._config[CONF_STATE_TOPIC],
                    "msg_callback": message_received,
                    "qos": self._config[CONF_QOS],
                }
            },
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._config[CONF_NAME]

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return ""

    @property
    def force_update(self):
        """Force update."""
        return False

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._device_attributes

    @property
    def state_attributes(self):
        """Return the state attributes"""
        return {"codes": G_RF_CODES}

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:stop"

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return None


# transfer b0 to b1 code
def get_b0_from_b1(b1):
    try:
        b1 = b1.replace(" ", "")
        iNbrOfBuckets = int(b1[4:6], 16)
        arrBuckets = []

        # Start packing
        sz_out_aux = " %0.2X " % iNbrOfBuckets
        sz_out_aux += "%0.2X " % int(8)

        for i in range(0, iNbrOfBuckets):
            sz_out_aux += b1[6 + i * 4 : 10 + i * 4] + " "
            arrBuckets.append(int(b1[6 + i * 4 : 10 + i * 4], 16))

        sz_out_aux += b1[10 + i * 4 : -2]

        szDataStr = sz_out_aux.replace(" ", "")
        sz_out_aux += " 55"
        iLength = int(len(szDataStr) / 2)
        sz_out_aux = "AA B0 " + "%0.2X" % iLength + sz_out_aux

        return sz_out_aux
    except Exception:
        _LOGGER.warning("Problem with b1 to b0 code transfer")
        return b1
