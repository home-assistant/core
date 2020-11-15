"""Publish simple item state changes via MQTT."""
import json

import voluptuous as vol

from homeassistant.components.mqtt import valid_publish_topic
from homeassistant.const import MATCH_ALL
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    convert_include_exclude_filter,
)
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.json import JSONEncoder

CONF_BASE_TOPIC = "base_topic"
CONF_PUBLISH_ATTRIBUTES = "publish_attributes"
CONF_PUBLISH_TIMESTAMPS = "publish_timestamps"

DOMAIN = "mqtt_statestream"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA.extend(
            {
                vol.Required(CONF_BASE_TOPIC): valid_publish_topic,
                vol.Optional(CONF_PUBLISH_ATTRIBUTES, default=False): cv.boolean,
                vol.Optional(CONF_PUBLISH_TIMESTAMPS, default=False): cv.boolean,
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the MQTT state feed."""
    conf = config.get(DOMAIN)
    publish_filter = convert_include_exclude_filter(conf)
    base_topic = conf.get(CONF_BASE_TOPIC)
    publish_attributes = conf.get(CONF_PUBLISH_ATTRIBUTES)
    publish_timestamps = conf.get(CONF_PUBLISH_TIMESTAMPS)
    if not base_topic.endswith("/"):
        base_topic = f"{base_topic}/"

    @callback
    def _state_publisher(entity_id, old_state, new_state):
        if new_state is None:
            return

        if not publish_filter(entity_id):
            return

        payload = new_state.state

        mybase = f"{base_topic}{entity_id.replace('.', '/')}/"
        hass.components.mqtt.async_publish(f"{mybase}state", payload, 1, True)

        if publish_timestamps:
            if new_state.last_updated:
                hass.components.mqtt.async_publish(
                    f"{mybase}last_updated", new_state.last_updated.isoformat(), 1, True
                )
            if new_state.last_changed:
                hass.components.mqtt.async_publish(
                    f"{mybase}last_changed", new_state.last_changed.isoformat(), 1, True
                )

        if publish_attributes:
            for key, val in new_state.attributes.items():
                encoded_val = json.dumps(val, cls=JSONEncoder)
                hass.components.mqtt.async_publish(mybase + key, encoded_val, 1, True)

    async_track_state_change(hass, MATCH_ALL, _state_publisher)
    return True
