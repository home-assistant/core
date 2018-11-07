"""
Helper to handle a set of topics to subscribe to.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt/
"""
import logging

from homeassistant.components import mqtt
from homeassistant.components.mqtt import DEFAULT_QOS, MessageCallbackType
from homeassistant.loader import bind_hass
from homeassistant.helpers.typing import (
    HomeAssistantType)

_LOGGER = logging.getLogger(__name__)


@bind_hass
async def async_subscribe_topics(hass: HomeAssistantType, sub_state: dict,
                                 new_topics: dict,
                                 msg_callback: MessageCallbackType,
                                 qos: int = DEFAULT_QOS,
                                 encoding: str = 'utf-8'):
    """(Re)Subscribe to a set of MQTT topics.

    State is kept in sub_state.
    """
    if sub_state is None:
        sub_state = {'topics': {}}
    old_topics = sub_state['topics']
    for key, sub in list(old_topics.items()):
        topic = sub[0]
        unsub = sub[1]
        if key not in new_topics or topic != new_topics[key]:
            if unsub is not None:
                unsub()
            del old_topics[key]
    for key, topic in new_topics.items():
        if key not in old_topics and topic is not None:
            unsub = await mqtt.async_subscribe(hass, topic, msg_callback, qos)
            old_topics[key] = (topic, unsub)

    return sub_state


@bind_hass
async def async_unsubscribe_topics(hass: HomeAssistantType, sub_state: dict):
    """Unsubscribe from all MQTT topics managed by async_subscribe_topics."""
    await async_subscribe_topics(hass, sub_state, {}, None)

    return sub_state
