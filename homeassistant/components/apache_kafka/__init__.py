"""Support for Apache Kafka."""
from datetime import datetime
import json
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_IP_ADDRESS, CONF_PORT, EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'apache_kafka'

CONF_FILTER = 'filter'
CONF_TOPIC = 'topic'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_TOPIC): cv.string,
        vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Activate the Apache Kafka integration."""
    from aiokafka import AIOKafkaProducer

    conf = config[DOMAIN]
    topic_name = conf[CONF_TOPIC]
    entities_filter = conf[CONF_FILTER]

    producer = AIOKafkaProducer(
        loop=hass.loop,
        bootstrap_servers="{0}:{1}".format(
            conf[CONF_IP_ADDRESS], conf[CONF_PORT]),
        compression_type="gzip",
    )

    encoder = DateTimeJSONEncoder()

    async def send_to_pubsub(event):
        """Send states to Pub/Sub."""
        await producer.start()

        state = event.data.get('new_state')
        if (state is None
                or state.state in (STATE_UNKNOWN, '', STATE_UNAVAILABLE)
                or not entities_filter(state.entity_id)):
            return

        as_dict = state.as_dict()
        data = json.dumps(
            obj=as_dict,
            default=encoder.encode
        ).encode('utf-8')

        try:
            await producer.send_and_wait(topic_name, data)
        finally:
            producer.stop()

    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, producer.stop())
    hass.bus.listen(EVENT_STATE_CHANGED, send_to_pubsub)

    return True


class DateTimeJSONEncoder(json.JSONEncoder):
    """Encode python objects.

    Additionally add encoding for datetime objects as isoformat.
    """

    def default(self, o):  # pylint: disable=E0202
        """Implement encoding logic."""
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)
