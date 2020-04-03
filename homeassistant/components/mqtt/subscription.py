"""Helper to handle a set of topics to subscribe to."""
import logging
from typing import Any, Callable, Dict, Optional

import attr

from homeassistant.components import mqtt
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import bind_hass

from . import debug_info
from .const import DEFAULT_QOS
from .models import MessageCallbackType

_LOGGER = logging.getLogger(__name__)


@attr.s(slots=True)
class EntitySubscription:
    """Class to hold data about an active entity topic subscription."""

    hass = attr.ib(type=HomeAssistantType)
    topic = attr.ib(type=str)
    message_callback = attr.ib(type=MessageCallbackType)
    unsubscribe_callback = attr.ib(type=Optional[Callable[[], None]])
    qos = attr.ib(type=int, default=0)
    encoding = attr.ib(type=str, default="utf-8")

    async def resubscribe_if_necessary(self, hass, other):
        """Re-subscribe to the new topic if necessary."""
        if not self._should_resubscribe(other):
            return

        if other is not None and other.unsubscribe_callback is not None:
            other.unsubscribe_callback()
            # Clear debug data if it exists
            debug_info.remove_topic(self.hass, other.message_callback, other.topic)

        if self.topic is None:
            # We were asked to remove the subscription or not to create it
            return

        # Prepare debug data
        debug_info.add_topic(self.hass, self.message_callback, self.topic)

        self.unsubscribe_callback = await mqtt.async_subscribe(
            hass, self.topic, self.message_callback, self.qos, self.encoding
        )

    def _should_resubscribe(self, other):
        """Check if we should re-subscribe to the topic using the old state."""
        if other is None:
            return True

        return (self.topic, self.qos, self.encoding) != (
            other.topic,
            other.qos,
            other.encoding,
        )


@bind_hass
async def async_subscribe_topics(
    hass: HomeAssistantType,
    new_state: Optional[Dict[str, EntitySubscription]],
    topics: Dict[str, Any],
):
    """(Re)Subscribe to a set of MQTT topics.

    State is kept in sub_state and a dictionary mapping from the subscription
    key to the subscription state.

    Please note that the sub state must not be shared between multiple
    sets of topics. Every call to async_subscribe_topics must always
    contain _all_ the topics the subscription state should manage.
    """
    current_subscriptions = new_state if new_state is not None else {}
    new_state = {}
    for key, value in topics.items():
        # Extract the new requested subscription
        requested = EntitySubscription(
            topic=value.get("topic", None),
            message_callback=value.get("msg_callback", None),
            unsubscribe_callback=None,
            qos=value.get("qos", DEFAULT_QOS),
            encoding=value.get("encoding", "utf-8"),
            hass=hass,
        )
        # Get the current subscription state
        current = current_subscriptions.pop(key, None)
        await requested.resubscribe_if_necessary(hass, current)
        new_state[key] = requested

    # Go through all remaining subscriptions and unsubscribe them
    for remaining in current_subscriptions.values():
        if remaining.unsubscribe_callback is not None:
            remaining.unsubscribe_callback()
            # Clear debug data if it exists
            debug_info.remove_topic(hass, remaining.message_callback, remaining.topic)

    return new_state


@bind_hass
async def async_unsubscribe_topics(hass: HomeAssistantType, sub_state: dict):
    """Unsubscribe from all MQTT topics managed by async_subscribe_topics."""
    return await async_subscribe_topics(hass, sub_state, {})
