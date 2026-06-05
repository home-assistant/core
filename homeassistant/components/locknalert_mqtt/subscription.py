"""Helper to handle a set of topics to subscribe to."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.core import HassJobType, HomeAssistant, callback

from .client import async_subscribe_internal
from .const import DEFAULT_ENCODING, DEFAULT_QOS
from .models import MessageCallbackType


@dataclass(slots=True, kw_only=True)
class EntitySubscription:
    """Active MQTT topic subscription bound to a single entity config key.

    Tracks whether the subscription needs to be created, kept, or replaced
    when an entity's configuration changes.  Instances are stored in a
    ``dict[str, EntitySubscription]`` keyed by the config field name
    (e.g. ``"state_topic"``).

    Attributes:
        hass (HomeAssistant): The Home Assistant instance.
        topic (str | None): MQTT topic to subscribe to, or ``None`` to skip.
        message_callback (MessageCallbackType): Called for each received message.
        should_subscribe (bool | None): Tracks whether a new subscription
            should be established.  ``None`` means not yet evaluated.
        unsubscribe_callback (Callable[[], None] | None): Cancels the active
            subscription when called.  ``None`` if not currently subscribed.
        qos (int): MQTT quality-of-service level (0, 1, or 2).
        encoding (str | None): Payload encoding, or ``None`` for raw bytes.
        entity_id (str | None): Entity id used for diagnostic logging.
        job_type (HassJobType | None): Execution model hint for the callback.
    """

    hass: HomeAssistant
    topic: str | None
    message_callback: MessageCallbackType
    should_subscribe: bool | None
    unsubscribe_callback: Callable[[], None] | None
    qos: int = 0
    encoding: str | None = DEFAULT_ENCODING
    entity_id: str | None
    job_type: HassJobType | None

    def resubscribe_if_necessary(
        self, _hass: HomeAssistant, other: EntitySubscription | None
    ) -> None:
        """Determine whether to keep, replace, or create the MQTT subscription.

        Compares this (desired) subscription against *other* (the previous
        subscription for the same config key).  If the topic, QoS, or encoding
        has changed, the old subscription is cancelled and this instance is
        marked for re-subscription.  If nothing changed, the existing
        unsubscribe callback is inherited so the live subscription is kept.

        Args:
            _hass (HomeAssistant): The Home Assistant instance (unused, kept for
                API consistency with dispatcher connect callbacks).
            other (EntitySubscription | None): The previous subscription state,
                or ``None`` if no subscription existed before.
        """
        if not self._should_resubscribe(other):
            if TYPE_CHECKING:
                assert other
            self.unsubscribe_callback = other.unsubscribe_callback
            return

        if other is not None and other.unsubscribe_callback is not None:
            other.unsubscribe_callback()

        if self.topic is None:
            # We were asked to remove the subscription or not to create it
            return

        # Prepare debug data
        self.should_subscribe = True

    @callback
    def subscribe(self) -> None:
        """Establish the MQTT subscription if one is pending.

        Called after :func:`resubscribe_if_necessary` has set
        ``should_subscribe = True``.  Registers the subscription with the
        underlying MQTT client and stores the returned unsubscribe callback.
        Does nothing if the subscription is not pending or if ``topic`` is empty.
        """
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
        """Return True if the subscription parameters have changed.

        A new subscription is required whenever the topic, QoS, or encoding
        differs from the previous state, or when no previous state exists.

        Args:
            other (EntitySubscription | None): The previous subscription state,
                or ``None`` if this is the first time the topic is configured.

        Returns:
            bool: ``True`` if a new subscription must be created, ``False`` if
                the existing subscription can be reused.
        """
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
    sub_state: dict[str, EntitySubscription] | None,
    topics: dict[str, dict[str, Any]],
) -> dict[str, EntitySubscription]:
    """Build a new subscription state, cancelling any topics that were removed.

    Compares *topics* (the desired subscriptions) against *sub_state* (the
    currently active subscriptions).  For each key in *topics* the previous
    :class:`EntitySubscription` (if any) is compared; subscriptions whose
    topic, QoS, or encoding changed are queued for replacement.  Any key that
    no longer appears in *topics* has its subscription cancelled immediately.

    Call :func:`async_subscribe_topics` after this function to actually
    register the pending subscriptions with the MQTT client.

    The returned dict must not be shared between independent sets of topics:
    every call must include **all** keys that the caller wants to manage.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        sub_state (dict[str, EntitySubscription] | None): The current
            subscription state, or ``None`` on first call.
        topics (dict[str, dict[str, Any]]): Desired subscriptions keyed by an
            arbitrary config-key name.  Each value is a dict with at least a
            ``"msg_callback"`` key and optionally ``"topic"``, ``"qos"``,
            ``"encoding"``, ``"entity_id"``, and ``"job_type"``.

    Returns:
        dict[str, EntitySubscription]: The updated subscription state to be
            passed to subsequent calls.
    """
    current_subscriptions: dict[str, EntitySubscription]
    current_subscriptions = sub_state if sub_state is not None else {}
    sub_state = {}
    for key, value in topics.items():
        # Extract the new requested subscription
        requested = EntitySubscription(
            topic=value.get("topic"),
            message_callback=value["msg_callback"],
            unsubscribe_callback=None,
            qos=value.get("qos", DEFAULT_QOS),
            encoding=value.get("encoding", DEFAULT_ENCODING),
            hass=hass,
            should_subscribe=None,
            entity_id=value.get("entity_id"),
            job_type=value.get("job_type"),
        )
        # Get the current subscription state
        current = current_subscriptions.pop(key, None)
        requested.resubscribe_if_necessary(hass, current)
        sub_state[key] = requested

    # Go through all remaining subscriptions and unsubscribe them
    for remaining in current_subscriptions.values():
        if remaining.unsubscribe_callback is not None:
            remaining.unsubscribe_callback()

    return sub_state


@callback
def async_subscribe_topics(
    hass: HomeAssistant,
    sub_state: dict[str, EntitySubscription],
) -> None:
    """Finalise pending subscriptions prepared by :func:`async_prepare_subscribe_topics`.

    Iterates over *sub_state* and calls :meth:`EntitySubscription.subscribe`
    on each entry that has been marked as needing a new subscription.

    Args:
        hass (HomeAssistant): The Home Assistant instance (passed through for
            API consistency; subscriptions are registered via the stored client).
        sub_state (dict[str, EntitySubscription]): Current subscription state
            returned by :func:`async_prepare_subscribe_topics`.
    """
    async_subscribe_topics_internal(hass, sub_state)


@callback
def async_subscribe_topics_internal(
    hass: HomeAssistant,
    sub_state: dict[str, EntitySubscription],
) -> None:
    """Activate pending subscriptions (internal API; do not call from outside this integration).

    Called by :func:`async_subscribe_topics` and by entity mixins that
    subscribe directly without going through the public helper.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        sub_state (dict[str, EntitySubscription]): Subscription state whose
            pending entries should be registered with the MQTT client.
    """
    for sub in sub_state.values():
        sub.subscribe()


if TYPE_CHECKING:

    def async_unsubscribe_topics(
        hass: HomeAssistant, sub_state: dict[str, EntitySubscription] | None
    ) -> dict[str, EntitySubscription]:
        """Cancel all subscriptions in *sub_state* and return an empty state dict.

        Convenience alias for calling :func:`async_prepare_subscribe_topics`
        with an empty *topics* dict, which cancels every active subscription.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            sub_state (dict[str, EntitySubscription] | None): The current
                subscription state, or ``None``.

        Returns:
            dict[str, EntitySubscription]: An empty subscription state dict.
        """


async_unsubscribe_topics = partial(async_prepare_subscribe_topics, topics={})
