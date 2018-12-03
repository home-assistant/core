"""
Helper to handle a set of topics to subscribe to.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt/
"""
import logging
from typing import Any, Callable, Dict, Optional

import attr

from homeassistant.components import mqtt
from homeassistant.components.mqtt import DEFAULT_QOS, MessageCallbackType
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)


@attr.s(slots=True)
class EntitySubscription:
    """Class to hold data about an active entity topic subscription."""

    topic = attr.ib(type=str)
    message_callback = attr.ib(type=MessageCallbackType)
    unsubscribe_callback = attr.ib(type=Optional[Callable[[], None]])
    qos = attr.ib(type=int, default=0)
    encoding = attr.ib(type=str, default='utf-8')

    def should_resubscribe(self, other):
        """Check if we should re-subscribe to the topic using the old state."""
        if other is None:
            return True

        return self.topic != other.topic or self.qos != other.qos or \
            self.encoding != other.encoding


@bind_hass
async def async_subscribe_topics(hass: HomeAssistantType,
                                 new_state: Optional[Dict[str,
                                                          EntitySubscription]],
                                 topics: Dict[str, Any]):
    """(Re)Subscribe to a set of MQTT topics.

    State is kept in sub_state and a dictionary mapping from the subscription
    key to the subscription state
    """
    current_subscriptions = new_state if new_state is not None else {}
    new_state = {}
    for key, value in topics.items():
        # Extract the new requested subscription
        requested = EntitySubscription(
            topic=value.get('topic', None),
            message_callback=value.get('msg_callback', None),
            unsubscribe_callback=None,
            qos=value.get('qos', DEFAULT_QOS),
            encoding=value.get('encoding', 'utf-8'),
        )
        # Get the current subscription state
        current = current_subscriptions.pop(key, None)

        # Re-subscribe if we need to
        if requested.should_resubscribe(current):
            if requested.unsubscribe_callback is not None:
                requested.unsubscribe_callback()
            requested.unsubscribe_callback = await mqtt.async_subscribe(
                hass, requested.topic, requested.message_callback,
                requested.qos, requested.encoding)
        new_state[key] = requested

    for remaining in current_subscriptions.values():
        if remaining.unsubscribe_callback is not None:
            remaining.unsubscribe_callback()

    return new_state


@bind_hass
async def async_unsubscribe_topics(hass: HomeAssistantType, sub_state: dict):
    """Unsubscribe from all MQTT topics managed by async_subscribe_topics."""
    await async_subscribe_topics(hass, sub_state, {})

    return sub_state
