"""Group platform for notify component."""
import asyncio
from collections import deque
from collections.abc import Mapping
from copy import deepcopy
import logging
import time

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    DOMAIN,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.components.switch import is_on
from homeassistant.const import ATTR_SERVICE, CONF_NAME
import homeassistant.helpers.config_validation as cv

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

CONF_SERVICES = "services"
CONF_SWITCH = "switch"
CONF_MAX_PER_MINUTE = "max_per_minute"
CONF_MAX_PER_HOUR = "max_per_hour"
CONF_MAX_PER_DAY = "max_per_day"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SERVICES): vol.All(
            cv.ensure_list,
            [{vol.Required(ATTR_SERVICE): cv.slug, vol.Optional(ATTR_DATA): dict}],
        ),
        vol.Optional(CONF_SWITCH): cv.entity_id,
        vol.Optional(CONF_MAX_PER_MINUTE): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(CONF_MAX_PER_HOUR): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(CONF_MAX_PER_DAY): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)


def update(input_dict, update_source):
    """Deep update a dictionary.

    Async friendly.
    """
    for key, val in update_source.items():
        if isinstance(val, Mapping):
            recurse = update(input_dict.get(key, {}), val)
            input_dict[key] = recurse
        else:
            input_dict[key] = update_source[key]
    return input_dict


async def async_get_service(hass, config, discovery_info=None):
    """Get the Group notification service."""
    return GroupNotifyPlatform(
        hass,
        config.get(CONF_NAME),
        config.get(CONF_SERVICES),
        config.get(CONF_SWITCH),
        config.get(CONF_MAX_PER_MINUTE),
        config.get(CONF_MAX_PER_HOUR),
        config.get(CONF_MAX_PER_DAY),
    )


class GroupNotifyPlatform(BaseNotificationService):
    """Implement the notification service for the group notify platform."""

    def __init__(
        self, hass, name, entities, switch, max_per_minute, max_per_hour, max_per_day
    ):
        """Initialize the service."""
        self.hass = hass
        self.name = name
        self.entities = entities
        self.switch = switch
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        self.lock = None
        if self.max_per_minute or self.max_per_hour or self.max_per_day:
            # we only push onto the deques that have rate limits
            self.calls_minute = deque()
            self.calls_hour = deque()
            self.calls_day = deque()
            self.lock = asyncio.Lock()

    def _calls_minute_span(self):
        if not self.calls_minute:
            return 0
        return self.calls_minute[-1] - self.calls_minute[0]

    def _calls_hour_span(self):
        if not self.calls_hour:
            return 0
        return self.calls_hour[-1] - self.calls_hour[0]

    def _calls_day_span(self):
        if not self.calls_day:
            return 0
        return self.calls_day[-1] - self.calls_day[0]

    def _rate_limit_gate(self):
        """Return true iff we are rate-limited."""
        answer = False
        if self.lock:
            with self.lock:
                # trim our deques for each time frame before testing len
                while self._calls_minute_span() >= 60:
                    self.calls_minute.popleft()
                while self._calls_hour_span() >= 3600:
                    self.calls_hour.popleft()
                while self._calls_day_span() >= 86400:
                    self.calls_day.popleft()

                # check length of each deque for each time frame
                if (
                    self.max_per_minute
                    and len(self.calls_minute) >= self.max_per_minute
                ):
                    _LOGGER.debug(
                        "%s rate-limited to %s/minute", self.name, self.max_per_minute
                    )
                    answer = True
                if self.max_per_hour and len(self.calls_hour) >= self.max_per_hour:
                    _LOGGER.debug(
                        "%s rate-limited to %s/hour", self.name, self.max_per_hour
                    )
                    answer = True
                if self.max_per_day and len(self.calls_day) >= self.max_per_day:
                    _LOGGER.debug(
                        "%s rate-limited to %s/day", self.name, self.max_per_day
                    )
                    answer = True

                # update each active deque
                current_time = time.time()
                if self.max_per_minute:
                    self.calls_minute.append(current_time)
                if self.max_per_hour:
                    self.calls_hour.append(current_time)
                if self.max_per_day:
                    self.calls_day.append(current_time)
        return answer

    async def async_send_message(self, message="", **kwargs):
        """Send message to all entities in the group."""
        if self.switch and not is_on(self.hass, self.switch):
            _LOGGER.debug(
                "Group notification %s blocked message due to switch off", self.name
            )
            return

        if self._rate_limit_gate():
            return

        payload = {ATTR_MESSAGE: message}
        payload.update({key: val for key, val in kwargs.items() if val})

        tasks = []
        for entity in self.entities:
            sending_payload = deepcopy(payload.copy())
            if entity.get(ATTR_DATA) is not None:
                update(sending_payload, entity.get(ATTR_DATA))
            tasks.append(
                self.hass.services.async_call(
                    DOMAIN, entity.get(ATTR_SERVICE), sending_payload
                )
            )

        if tasks:
            await asyncio.wait(tasks)
