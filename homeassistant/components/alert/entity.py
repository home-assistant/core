"""Support for repeating alerts when conditions are met."""

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
from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.template import Template
from homeassistant.util.dt import now

from .const import DOMAIN, LOGGER


class AlertEntity(Entity):
    """Representation of an alert."""

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
                await self.hass.services.async_call(
                    DOMAIN_NOTIFY, target, msg_payload, context=self._context
                )
            except ServiceNotFound:
                LOGGER.error(
                    "Failed to call notify.%s, retrying at next notification interval",
                    target,
                )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Async Unacknowledge alert."""
        LOGGER.debug("Reset Alert: %s", self._attr_name)
        self._ack = False
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Async Acknowledge alert."""
        LOGGER.debug("Acknowledged Alert: %s", self._attr_name)
        self._ack = True
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Async toggle alert."""
        if self._ack:
            return await self.async_turn_on()
        return await self.async_turn_off()
