"""Support for repeating alerts when conditions are met.

DEVELOPMENT OF THE ALERT INTEGRATION IS FROZEN.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as DOMAIN_NOTIFY,
)
from homeassistant.const import STATE_IDLE, STATE_OFF, STATE_ON
from homeassistant.core import Event, EventStateChangedData, HassJob, HomeAssistant
from homeassistant.exceptions import ServiceNotFound, ServiceValidationError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.template import Template
from homeassistant.util.dt import now

from .const import DOMAIN, LOGGER


class AlertEntity(Entity):
    """Representation of an alert.

    DEVELOPMENT OF THE ALERT INTEGRATION IS FROZEN.
    """

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str,
        name: str,
        watched_entity_id: str,
        state: str,
        repeat: list[float],
        skip_first: bool,
        message_template: Template | None,
        done_message_template: Template | None,
        notifiers: list[str],
        can_ack: bool,
        title_template: Template | None,
        data: dict[Any, Any],
    ) -> None:
        """Initialize the alert."""
        self.hass = hass
        self._attr_name = name
        self._alert_state = state
        self._skip_first = skip_first
        self._data = data

        self._message_template = message_template
        self._done_message_template = done_message_template
        self._title_template = title_template

        self._notifiers = notifiers
        self._can_ack = can_ack

        self._delay = [timedelta(minutes=val) for val in repeat]
        self._next_delay = 0

        self._firing = False
        self._ack = False
        self._cancel: Callable[[], None] | None = None
        self._send_done_message = False
        self.entity_id = f"{DOMAIN}.{entity_id}"

        async_track_state_change_event(
            hass, [watched_entity_id], self.watched_entity_change
        )

    @property
    def state(self) -> str:
        """Return the alert status."""
        if self._firing:
            if self._ack:
                return STATE_OFF
            return STATE_ON
        return STATE_IDLE

    async def watched_entity_change(self, event: Event[EventStateChangedData]) -> None:
        """Determine if the alert should start or stop."""
        if (to_state := event.data["new_state"]) is None:
            return
        LOGGER.debug("Watched entity (%s) has changed", event.data["entity_id"])
        if to_state.state == self._alert_state and not self._firing:
            await self.begin_alerting()
        if to_state.state != self._alert_state and self._firing:
            await self.end_alerting()

    async def begin_alerting(self) -> None:
        """Begin the alert procedures."""
        LOGGER.debug("Beginning Alert: %s", self._attr_name)
        self._ack = False
        self._firing = True
        self._next_delay = 0

        if not self._skip_first:
            await self._notify()
        else:
            await self._schedule_notify()

        self.async_write_ha_state()

    async def end_alerting(self) -> None:
        """End the alert procedures."""
        LOGGER.debug("Ending Alert: %s", self._attr_name)
        if self._cancel is not None:
            self._cancel()
            self._cancel = None

        self._ack = False
        self._firing = False
        if self._send_done_message:
            await self._notify_done_message()
        self.async_write_ha_state()

    async def _schedule_notify(self) -> None:
        """Schedule a notification."""
        delay = self._delay[self._next_delay]
        next_msg = now() + delay
        self._cancel = async_track_point_in_time(
            self.hass,
            HassJob(
                self._notify, name="Schedule notify alert", cancel_on_shutdown=True
            ),
            next_msg,
        )
        self._next_delay = min(self._next_delay + 1, len(self._delay) - 1)

    async def _notify(self, *args: Any) -> None:
        """Send the alert notification."""
        if not self._firing:
            return

        if not self._ack:
            LOGGER.info("Alerting: %s", self._attr_name)
            self._send_done_message = True

            if self._message_template is not None:
                message = self._message_template.async_render(parse_result=False)
            else:
                message = self._attr_name

            await self._send_notification_message(message)
        await self._schedule_notify()

    async def _notify_done_message(self) -> None:
        """Send notification of complete alert."""
        LOGGER.info("Alerting: %s", self._done_message_template)
        self._send_done_message = False

        if self._done_message_template is None:
            return

        message = self._done_message_template.async_render(parse_result=False)

        await self._send_notification_message(message)

    async def _send_notification_message(self, message: Any) -> None:
        if not self._notifiers:
            return

        msg_payload = {ATTR_MESSAGE: message}

        if self._title_template is not None:
            title = self._title_template.async_render(parse_result=False)
            msg_payload[ATTR_TITLE] = title
        if self._data:
            msg_payload[ATTR_DATA] = self._data

        LOGGER.debug(msg_payload)

        for target in self._notifiers:
            try:
                # Determine if this is an entity ID or a legacy service name
                # Entity IDs typically have underscores and are longer (e.g., home_assistant_alerts_fons_64366733)
                # Legacy service names are shorter (e.g., telegram, mobile_app)
                # Check if target looks like an entity ID (contains multiple underscores or starts with home_assistant)
                is_entity_id = (
                    ("_" in target and target.count("_") >= 2)
                    or target.startswith("home_assistant")
                    or target.startswith("notify.")
                )

                if is_entity_id:
                    # Use the new notify.send_message service with entity ID
                    # Ensure entity_id has the notify. prefix
                    entity_id = (
                        target if target.startswith("notify.") else f"notify.{target}"
                    )
                    import asyncio

                    # Check if entity exists
                    entity_state = self.hass.states.get(entity_id)
                    has_send_message = self.hass.services.has_service(
                        DOMAIN_NOTIFY, "send_message"
                    )

                    # Wait up to 5 seconds for entity to exist
                    max_wait = 5
                    wait_interval = 0.5
                    waited = 0
                    while entity_state is None and waited < max_wait:
                        await asyncio.sleep(wait_interval)
                        waited += wait_interval
                        entity_state = self.hass.states.get(entity_id)
                        has_send_message = self.hass.services.has_service(
                            DOMAIN_NOTIFY, "send_message"
                        )

                    if entity_state is None:
                        LOGGER.warning(
                            "Alert: Entity %s does not exist after waiting, skipping notification",
                            entity_id,
                        )
                        continue

                    if not has_send_message:
                        LOGGER.warning(
                            "Alert: Service notify.send_message not available, skipping notification"
                        )
                        continue

                    # The service name is "send_message", not "notify.send_message"
                    # Entity services need the entity_id in the service data
                    await self.hass.services.async_call(
                        DOMAIN_NOTIFY,
                        "send_message",
                        {**msg_payload, "entity_id": entity_id},
                        context=self._context,
                    )
                else:
                    # Legacy service call for backward compatibility
                    await self.hass.services.async_call(
                        DOMAIN_NOTIFY, target, msg_payload, context=self._context
                    )
            except ServiceNotFound:
                LOGGER.error(
                    "Failed to call notify.%s, retrying at next notification interval",
                    target,
                )
            except ServiceValidationError as e:
                LOGGER.error(
                    "Service validation error calling notify.%s: %s",
                    target,
                    e,
                    exc_info=True,
                )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Async Unacknowledge alert."""
        LOGGER.debug("Reset Alert: %s", self._attr_name)
        self._ack = False
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Async Acknowledge alert."""
        if not self._can_ack:
            raise ServiceValidationError("This alert cannot be acknowledged")
        self._ack = True
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Async toggle alert."""
        if self._ack:
            return await self.async_turn_on()
        return await self.async_turn_off()
