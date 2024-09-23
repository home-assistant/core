"""Helper to handle a set of topics to subscribe to."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.core import HassJobType, HomeAssistant, callback

from . import debug_info
from .client import async_subscribe_internal
from .const import DEFAULT_QOS
from .models import MessageCallbackType


@dataclass(slots=True, kw_only=True)
class EntitySubscription:
    """Class to hold data about an active entity topic subscription."""

    hass: HomeAssistant
    topic: str | None
    message_callback: MessageCallbackType
    should_subscribe: bool | None
    unsubscribe_callback: Callable[[], None] | None
    qos: int = 0
    encoding: str = "utf-8"
    entity_id: str | None
    job_type: HassJobType | None

    def resubscribe_if_necessary(
        self, hass: HomeAssistant, other: EntitySubscription | None
    ) -> None:
        """Re-subscribe to the new topic if necessary."""
        if not self._should_resubscribe(other):
            if TYPE_CHECKING:
                assert other
            self.unsubscribe_callback = other.unsubscribe_callback
            return

        if other is not None and other.unsubscribe_callback is not None:
            other.unsubscribe_callback()
            # Clear debug data if it exists
            debug_info.remove_subscription(self.hass, str(other.topic), other.entity_id)

        if self.topic is None:
            # We were asked to remove the subscription or not to create it
            return

        # Prepare debug data
        debug_info.add_subscription(self.hass, self.topic, self.entity_id)

        self.should_subscribe = True

    @callback
    def subscribe(self) -> None:
        """Subscribe to a topic."""
        if not self.should_subscribe or not self.topic:
            return
        self.unsubscribe_callback = async_subscribe_internal(
            self.hass,
            self.topic,
            self.message_callback,
            self.qos,
            self.encoding,
            self.job_type,
        )

    def _should_resubscribe(self, other: EntitySubscription | None) -> bool:
        """Check if we should re-subscribe to the topic using the old state."""
        if other is None:
            return True

        return (
            self.topic,
            self.qos,
            self.encoding,
        ) != (
            other.topic,
            other.qos,
            other.encoding,
        )


@callback
def async_prepare_subscribe_topics(
    hass: HomeAssistant,
    new_state: dict[str, EntitySubscription] | None,
    topics: dict[str, dict[str, Any]],
) -> dict[str, EntitySubscription]:
    """Prepare (re)subscribe to a set of MQTT topics.

    State is kept in sub_state and a dictionary mapping from the subscription
    key to the subscription state.

    After this function has been called, async_subscribe_topics must be called to
    finalize any new subscriptions.

    Please note that the sub state must not be shared between multiple
    sets of topics. Every call to async_subscribe_topics must always
    contain _all_ the topics the subscription state should manage.
    """
    current_subscriptions = new_state if new_state is not None else {}
    new_state = {}
    for key, value in topics.items():
        # Extract the new requested subscription
        requested = EntitySubscription(
            topic=value.get("topic"),
            message_callback=value["msg_callback"],
            unsubscribe_callback=None,
            qos=value.get("qos", DEFAULT_QOS),
            encoding=value.get("encoding", "utf-8"),
            hass=hass,
            should_subscribe=None,
            entity_id=value.get("entity_id"),
            job_type=value.get("job_type"),
        )
        # Get the current subscription state
        current = current_subscriptions.pop(key, None)
        requested.resubscribe_if_necessary(hass, current)
        new_state[key] = requested

    # Go through all remaining subscriptions and unsubscribe them
    for remaining in current_subscriptions.values():
        if remaining.unsubscribe_callback is not None:
            remaining.unsubscribe_callback()
            # Clear debug data if it exists
            debug_info.remove_subscription(
                hass,
                str(remaining.topic),
                remaining.entity_id,
            )

    return new_state


async def async_subscribe_topics(
    hass: HomeAssistant,
    sub_state: dict[str, EntitySubscription],
) -> None:
    """(Re)Subscribe to a set of MQTT topics."""
    async_subscribe_topics_internal(hass, sub_state)


@callback
def async_subscribe_topics_internal(
    hass: HomeAssistant,
    sub_state: dict[str, EntitySubscription],
) -> None:
    """(Re)Subscribe to a set of MQTT topics.

    This function is internal to the MQTT integration and should not be called
    from outside the integration.
    """
    for sub in sub_state.values():
        sub.subscribe()


if TYPE_CHECKING:

    def async_unsubscribe_topics(
        hass: HomeAssistant, sub_state: dict[str, EntitySubscription] | None
    ) -> dict[str, EntitySubscription]:
        """Unsubscribe from all MQTT topics managed by async_subscribe_topics."""


async_unsubscribe_topics = partial(async_prepare_subscribe_topics, topics={})
