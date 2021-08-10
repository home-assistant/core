"""Helper to handle a set of topics to subscribe to."""
from __future__ import annotations

from typing import Any, Callable

import attr

from homeassistant.core import HomeAssistant
from homeassistant.loader import bind_hass

from . import debug_info
from .. import mqtt
from .const import DEFAULT_QOS
from .models import MessageCallbackType


@attr.s(slots=True)
class EntitySubscription:
    """Class to hold data about an active entity topic subscription."""

    hass: HomeAssistant = attr.ib()
    topic: str = attr.ib()
    message_callback: MessageCallbackType = attr.ib()
    unsubscribe_callback: Callable[[], None] | None = attr.ib()
    qos: int = attr.ib(default=0)
    encoding: str = attr.ib(default="utf-8")

    async def resubscribe_if_necessary(self, hass, other):
        """Re-subscribe to the new topic if necessary."""
        if not self._should_resubscribe(other):
            self.unsubscribe_callback = other.unsubscribe_callback
            return

        if other is not None and other.unsubscribe_callback is not None:
            other.unsubscribe_callback()
            # Clear debug data if it exists
            debug_info.remove_subscription(
                self.hass, other.message_callback, other.topic
            )

        if self.topic is None:
            # We were asked to remove the subscription or not to create it
            return

        # Prepare debug data
        debug_info.add_subscription(self.hass, self.message_callback, self.topic)

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
    hass: HomeAssistant,
    new_state: dict[str, EntitySubscription] | None,
    topics: dict[str, Any],
) -> dict[str, EntitySubscription]:
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
            debug_info.remove_subscription(
                hass, remaining.message_callback, remaining.topic
            )

    return new_state


@bind_hass
async def async_unsubscribe_topics(
    hass: HomeAssistant, sub_state: dict[str, EntitySubscription] | None
) -> dict[str, EntitySubscription]:
    """Unsubscribe from all MQTT topics managed by async_subscribe_topics."""
    return await async_subscribe_topics(hass, sub_state, {})
