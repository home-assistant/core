"""Support for Apache Kafka."""
from datetime import datetime
import json
import logging

from aiokafka import AIOKafkaProducer
import voluptuous as vol

from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA

_LOGGER = logging.getLogger(__name__)

DOMAIN = "apache_kafka"

CONF_FILTER = "filter"
CONF_TOPIC = "topic"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Required(CONF_TOPIC): cv.string,
                vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Activate the Apache Kafka integration."""
    conf = config[DOMAIN]

    kafka = hass.data[DOMAIN] = KafkaManager(
        hass,
        conf[CONF_IP_ADDRESS],
        conf[CONF_PORT],
        conf[CONF_TOPIC],
        conf[CONF_FILTER],
    )

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, kafka.shutdown())

    await kafka.start()

    return True


class DateTimeJSONEncoder(json.JSONEncoder):
    """Encode python objects.

    Additionally add encoding for datetime objects as isoformat.
    """

    def default(self, o):  # pylint: disable=method-hidden
        """Implement encoding logic."""
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


class KafkaManager:
    """Define a manager to buffer events to Kafka."""

    def __init__(self, hass, ip_address, port, topic, entities_filter):
        """Initialize."""
        self._encoder = DateTimeJSONEncoder()
        self._entities_filter = entities_filter
        self._hass = hass
        self._producer = AIOKafkaProducer(
            loop=hass.loop,
            bootstrap_servers=f"{ip_address}:{port}",
            compression_type="gzip",
        )
        self._topic = topic

    def _encode_event(self, event):
        """Translate events into a binary JSON payload."""
        state = event.data.get("new_state")
        if (
            state is None
            or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE)
            or not self._entities_filter(state.entity_id)
        ):
            return

        return json.dumps(obj=state.as_dict(), default=self._encoder.encode).encode(
            "utf-8"
        )

    async def start(self):
        """Start the Kafka manager."""
        self._hass.bus.async_listen(EVENT_STATE_CHANGED, self.write)
        await self._producer.start()

    async def shutdown(self):
        """Shut the manager down."""
        await self._producer.stop()

    async def write(self, event):
        """Write a binary payload to Kafka."""
        payload = self._encode_event(event)

        if payload:
            await self._producer.send_and_wait(self._topic, payload)
