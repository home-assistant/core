"""Publish simple item state changes via MQTT."""
import json

import voluptuous as vol

from homeassistant.components.mqtt import valid_publish_topic
from homeassistant.const import (
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    MATCH_ALL,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import generate_filter
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.json import JSONEncoder

CONF_BASE_TOPIC = "base_topic"
CONF_PUBLISH_ATTRIBUTES = "publish_attributes"
CONF_PUBLISH_TIMESTAMPS = "publish_timestamps"

DOMAIN = "mqtt_statestream"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_EXCLUDE, default={}): vol.Schema(
                    {
                        vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
                        vol.Optional(CONF_DOMAINS, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }
                ),
                vol.Optional(CONF_INCLUDE, default={}): vol.Schema(
                    {
                        vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
                        vol.Optional(CONF_DOMAINS, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }
                ),
                vol.Required(CONF_BASE_TOPIC): valid_publish_topic,
                vol.Optional(CONF_PUBLISH_ATTRIBUTES, default=False): cv.boolean,
                vol.Optional(CONF_PUBLISH_TIMESTAMPS, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the MQTT state feed."""
    conf = config.get(DOMAIN, {})
    base_topic = conf.get(CONF_BASE_TOPIC)
    pub_include = conf.get(CONF_INCLUDE, {})
    pub_exclude = conf.get(CONF_EXCLUDE, {})
    publish_attributes = conf.get(CONF_PUBLISH_ATTRIBUTES)
    publish_timestamps = conf.get(CONF_PUBLISH_TIMESTAMPS)
    publish_filter = generate_filter(
        pub_include.get(CONF_DOMAINS, []),
        pub_include.get(CONF_ENTITIES, []),
        pub_exclude.get(CONF_DOMAINS, []),
        pub_exclude.get(CONF_ENTITIES, []),
    )
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
