"""
Helper to handle a set of topics to subscribe to.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt/
"""
import logging

from homeassistant.components import mqtt
from homeassistant.components.mqtt import DEFAULT_QOS
from homeassistant.loader import bind_hass
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)


@bind_hass
async def async_subscribe_topics(hass: HomeAssistantType, sub_state: dict,
                                 topics: dict):
    """(Re)Subscribe to a set of MQTT topics.

    State is kept in sub_state.
    """
    cur_state = sub_state if sub_state is not None else {}
    sub_state = {}
    for key in topics:
        topic = topics[key].get('topic', None)
        msg_callback = topics[key].get('msg_callback', None)
        qos = topics[key].get('qos', DEFAULT_QOS)
        encoding = topics[key].get('encoding', 'utf-8')
        topic = (topic, msg_callback, qos, encoding)
        (cur_topic, unsub) = cur_state.pop(
            key, ((None, None, None, None), None))

        if topic != cur_topic and topic[0] is not None:
            if unsub is not None:
                unsub()
            unsub = await mqtt.async_subscribe(
                hass, topic[0], topic[1], topic[2], topic[3])
        sub_state[key] = (topic, unsub)

    for key, (topic, unsub) in list(cur_state.items()):
        if unsub is not None:
            unsub()

    return sub_state


@bind_hass
async def async_unsubscribe_topics(hass: HomeAssistantType, sub_state: dict):
    """Unsubscribe from all MQTT topics managed by async_subscribe_topics."""
    await async_subscribe_topics(hass, sub_state, {})

    return sub_state
