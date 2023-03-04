"""Support for repeating alerts when conditions are met."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, final

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as DOMAIN_NOTIFY,
)
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_REPEAT,
    CONF_STATE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.dt import as_local, now, parse_datetime

from .const import (
    ATTR_SNOOZE_UNTIL,
    CONF_ALERT_MESSAGE,
    CONF_CAN_ACK,
    CONF_DATA,
    CONF_DONE_MESSAGE,
    CONF_NOTIFIERS,
    CONF_SKIP_FIRST,
    CONF_TITLE,
    DEFAULT_CAN_ACK,
    DEFAULT_SKIP_FIRST,
    DOMAIN,
    LOGGER,
    NOTIFICATION_SNOOZE,
    SERVICE_NOTIFICATION_CONTROL,
    SNOOZE_NOTIFICATIONS_DISABLED,
    SNOOZE_NOTIFICATIONS_ENABLED,
)

ALERT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_STATE, default=STATE_ON): cv.string,
        vol.Required(CONF_REPEAT): vol.All(
            cv.ensure_list,
            [vol.Coerce(float)],
            # Minimum delay is 1 second = 0.016 minutes
            [vol.Range(min=0.016)],
        ),
        vol.Optional(CONF_CAN_ACK, default=DEFAULT_CAN_ACK): cv.boolean,
        vol.Optional(CONF_SKIP_FIRST, default=DEFAULT_SKIP_FIRST): cv.boolean,
        vol.Optional(CONF_ALERT_MESSAGE): cv.template,
        vol.Optional(CONF_DONE_MESSAGE): cv.template,
        vol.Optional(CONF_TITLE): cv.template,
        vol.Optional(CONF_DATA): dict,
        vol.Optional(CONF_NOTIFIERS, default=list): vol.All(
            cv.ensure_list, [cv.string]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.schema_with_slug_keys(ALERT_SCHEMA)}, extra=vol.ALLOW_EXTRA
)
NOTIFICATION_CONTROL_SCHEMA = {
    vol.Required("enable"): vol.Any(STATE_ON, STATE_OFF, NOTIFICATION_SNOOZE),
    vol.Optional("snooze_hours"): vol.All(vol.Coerce(float), vol.Range(min=0)),
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Alert component."""
    component = EntityComponent[Alert](LOGGER, DOMAIN, hass)

    entities: list[Alert] = []

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        name = cfg[CONF_NAME]
        watched_entity_id = cfg[CONF_ENTITY_ID]
        alert_state = cfg[CONF_STATE]
        repeat = cfg[CONF_REPEAT]
        skip_first = cfg[CONF_SKIP_FIRST]
        message_template = cfg.get(CONF_ALERT_MESSAGE)
        done_message_template = cfg.get(CONF_DONE_MESSAGE)
        notifiers = cfg[CONF_NOTIFIERS]
        can_ack = cfg[CONF_CAN_ACK]
        title_template = cfg.get(CONF_TITLE)
        data = cfg.get(CONF_DATA)

        entities.append(
            Alert(
                hass,
                object_id,
                name,
                watched_entity_id,
                alert_state,
                repeat,
                skip_first,
                message_template,
                done_message_template,
                notifiers,
                can_ack,
                title_template,
                data,
            )
        )

    if not entities:
        return False

    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")
    component.async_register_entity_service(SERVICE_TURN_ON, {}, "async_turn_on")
    component.async_register_entity_service(SERVICE_TOGGLE, {}, "async_toggle")
    component.async_register_entity_service(
        SERVICE_NOTIFICATION_CONTROL,
        cv.make_entity_service_schema(NOTIFICATION_CONTROL_SCHEMA),
        "async_notification_control",
    )

    await component.async_add_entities(entities)

    return True


class Alert(RestoreEntity):
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
        if self._message_template is not None:
            self._message_template.hass = hass

        self._done_message_template = done_message_template
        if self._done_message_template is not None:
            self._done_message_template.hass = hass

        self._title_template = title_template
        if self._title_template is not None:
            self._title_template.hass = hass

        self._notifiers = notifiers
        self._can_ack = can_ack

        # While an alert is firing, delay and _next_delay represent the time until
        # the next notification will be sent.
        self._delay = [timedelta(minutes=val) for val in repeat]
        self._next_delay = 0

        # _snooze_until will be either:
        #   SNOOZE_NOTIFICATIONS_ENABLED
        #   SNOOZE_NOTIFICATIONS_DISABLED
        #   a datetime until which no notifications will be sent.
        self._snooze_until: datetime | str = SNOOZE_NOTIFICATIONS_ENABLED
        self._snooze_until_cancel: Callable[[], None] | None = None

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

    async def watched_entity_change(self, event: Event) -> None:
        """Determine if the alert should start or stop."""
        if (to_state := event.data.get("new_state")) is None:
            return
        LOGGER.debug("Watched entity (%s) has changed", event.data.get("entity_id"))
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

        if self._snooze_until is SNOOZE_NOTIFICATIONS_ENABLED:
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
        if self._snooze_until is SNOOZE_NOTIFICATIONS_ENABLED:
            if self._send_done_message:
                await self._notify_done_message()
        self.async_write_ha_state()

    async def async_notification_control(
        self, enable: str, snooze_hours: float | None = None
    ) -> None:
        """Enable, disable or snooze notifications, for current and future alerts."""
        LOGGER.debug(
            "async_notification_control: %s enable=%s snooze_hours=%s",
            self._attr_name,
            enable,
            snooze_hours,
        )
        if (snooze_hours is not None) != (enable == NOTIFICATION_SNOOZE):
            raise vol.Invalid(
                "snooze_hours parameter should be present only when 'enable' is "
                f"set to '{NOTIFICATION_SNOOZE}'"
            )

        if self._snooze_until_cancel is not None:
            self._snooze_until_cancel()
            self._snooze_until_cancel = None
        if self._cancel is not None:
            self._cancel()
            self._cancel = None

        if enable == STATE_OFF:
            LOGGER.debug("Disabling notifications for alert %s", self._attr_name)
            self._snooze_until = SNOOZE_NOTIFICATIONS_DISABLED
            self.async_write_ha_state()
        elif enable == STATE_ON:
            LOGGER.debug("Enabling notifications for alert %s", self._attr_name)
            self._snooze_until = SNOOZE_NOTIFICATIONS_ENABLED
            if self._firing:
                await self.begin_alerting()
            else:
                self.async_write_ha_state()
        else:  # enable == NOTIFICATION_SNOOZE, enforced by NOTIFICATION_CONTROL_SCHEMA
            LOGGER.debug(
                "Snoozing notifications for alert %s for %f hours",
                self._attr_name,
                snooze_hours,
            )
            assert isinstance(snooze_hours, float)  # checked above
            self._snooze_until = now() + timedelta(hours=snooze_hours)

            async def snooze_timeout(adt: datetime) -> None:
                self._snooze_until_cancel = None
                await self.async_notification_control(STATE_ON)

            self._snooze_until_cancel = async_track_point_in_time(
                self.hass, snooze_timeout, self._snooze_until
            )
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore extra state attributes on start-up."""
        await super().async_added_to_hass()

        # Restore _snooze_until from previous run
        if not (last_state := await self.async_get_last_state()):
            return
        if ATTR_SNOOZE_UNTIL in last_state.attributes:
            last_snooze_until = last_state.attributes.get(ATTR_SNOOZE_UNTIL)
            if last_snooze_until == SNOOZE_NOTIFICATIONS_ENABLED:
                await self.async_notification_control(STATE_ON)
            elif last_snooze_until == SNOOZE_NOTIFICATIONS_DISABLED:
                await self.async_notification_control(STATE_OFF)
            else:
                # _snooze_until from previous runs should be either
                # one of the two strings just tested above, or a
                # stringified datetime.
                adt = parse_datetime(str(last_snooze_until))
                if adt is None:
                    await self.async_notification_control(STATE_ON)
                else:
                    adt = as_local(adt)
                    hours = (adt - now()).total_seconds() / (60 * 60)
                    if hours <= 0:
                        await self.async_notification_control(STATE_ON)
                    else:
                        await self.async_notification_control(
                            NOTIFICATION_SNOOZE, hours
                        )

    @final
    @property
    def state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        return {ATTR_SNOOZE_UNTIL: self._snooze_until}

    async def _schedule_notify(self) -> None:
        """Schedule a notification."""
        delay = self._delay[self._next_delay]
        next_msg = now() + delay
        self._cancel = async_track_point_in_time(self.hass, self._notify, next_msg)
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
            await self.hass.services.async_call(
                DOMAIN_NOTIFY, target, msg_payload, context=self._context
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
