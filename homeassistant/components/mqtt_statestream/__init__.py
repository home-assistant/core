"""Publish simple item state changes via MQTT."""
import asyncio
import json

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.mqtt import valid_publish_topic
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    MATCH_ALL,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    CoreState,
    Event,
    HomeAssistant,
    State,
    callback,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    convert_include_exclude_filter,
)
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.typing import ConfigType

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the MQTT state feed."""
    callback_handler: CALLBACK_TYPE

    conf: ConfigType = config[DOMAIN]
    publish_filter = convert_include_exclude_filter(conf)
    base_topic: str = conf[CONF_BASE_TOPIC]
    publish_attributes: bool = conf[CONF_PUBLISH_ATTRIBUTES]
    publish_timestamps: bool = conf[CONF_PUBLISH_TIMESTAMPS]
    ha_started = asyncio.Event()
    if not base_topic.endswith("/"):
        base_topic = f"{base_topic}/"

    async def _state_publisher(
        entity_id: str, old_state: State | None, new_state: State | None
    ) -> None:
        if not ha_started.is_set():
            return

        if new_state is None:
            return

        if not publish_filter(entity_id):
            return

        payload = new_state.state

        mybase = f"{base_topic}{entity_id.replace('.', '/')}/"
        await mqtt.async_publish(hass, f"{mybase}state", payload, 1, True)

        if publish_timestamps:
            if new_state.last_updated:
                await mqtt.async_publish(
                    hass,
                    f"{mybase}last_updated",
                    new_state.last_updated.isoformat(),
                    1,
                    True,
                )
            if new_state.last_changed:
                await mqtt.async_publish(
                    hass,
                    f"{mybase}last_changed",
                    new_state.last_changed.isoformat(),
                    1,
                    True,
                )

        if publish_attributes:
            for key, val in new_state.attributes.items():
                encoded_val = json.dumps(val, cls=JSONEncoder)
                await mqtt.async_publish(hass, mybase + key, encoded_val, 1, True)

    if hass.state == CoreState.running:
        ha_started.set()
    else:

        @callback
        def _ha_started(_: Event) -> None:
            ha_started.set()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _ha_started)

    @callback
    def _ha_stopping(_: Event) -> None:
        callback_handler()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _ha_stopping)

    callback_handler = async_track_state_change(hass, MATCH_ALL, _state_publisher)
    return True
