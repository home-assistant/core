"""Support to interface with universal remote control devices."""
from datetime import timedelta
import functools as ft
import logging
from typing import Any, Iterable, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    make_entity_service_schema,
)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.loader import bind_hass

# mypy: allow-untyped-calls

_LOGGER = logging.getLogger(__name__)

ATTR_ACTIVITY = "activity"
ATTR_COMMAND = "command"
ATTR_DEVICE = "device"
ATTR_NUM_REPEATS = "num_repeats"
ATTR_DELAY_SECS = "delay_secs"
ATTR_HOLD_SECS = "hold_secs"
ATTR_ALTERNATIVE = "alternative"
ATTR_TIMEOUT = "timeout"

DOMAIN = "remote"
SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

SERVICE_SEND_COMMAND = "send_command"
SERVICE_LEARN_COMMAND = "learn_command"
SERVICE_SYNC = "sync"

DEFAULT_NUM_REPEATS = 1
DEFAULT_DELAY_SECS = 0.4
DEFAULT_HOLD_SECS = 0

SUPPORT_LEARN_COMMAND = 1

REMOTE_SERVICE_ACTIVITY_SCHEMA = make_entity_service_schema(
    {vol.Optional(ATTR_ACTIVITY): cv.string}
)


@bind_hass
def is_on(hass: HomeAssistantType, entity_id: str) -> bool:
    """Return if the remote is on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Track states and offer events for remotes."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_OFF, REMOTE_SERVICE_ACTIVITY_SCHEMA, "async_turn_off"
    )

    component.async_register_entity_service(
        SERVICE_TURN_ON, REMOTE_SERVICE_ACTIVITY_SCHEMA, "async_turn_on"
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE, REMOTE_SERVICE_ACTIVITY_SCHEMA, "async_toggle"
    )

    component.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        {
            vol.Required(ATTR_COMMAND): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_DEVICE): cv.string,
            vol.Optional(
                ATTR_NUM_REPEATS, default=DEFAULT_NUM_REPEATS
            ): cv.positive_int,
            vol.Optional(ATTR_DELAY_SECS): vol.Coerce(float),
            vol.Optional(ATTR_HOLD_SECS, default=DEFAULT_HOLD_SECS): vol.Coerce(float),
        },
        "async_send_command",
    )

    component.async_register_entity_service(
        SERVICE_LEARN_COMMAND,
        {
            vol.Optional(ATTR_DEVICE): cv.string,
            vol.Optional(ATTR_COMMAND): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_ALTERNATIVE): cv.boolean,
            vol.Optional(ATTR_TIMEOUT): cv.positive_int,
        },
        "async_learn_command",
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return cast(
        bool, await cast(EntityComponent, hass.data[DOMAIN]).async_setup_entry(entry)
    )


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await cast(EntityComponent, hass.data[DOMAIN]).async_unload_entry(entry)


class RemoteDevice(ToggleEntity):
    """Representation of a remote."""

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return 0

    def send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands to a device."""
        raise NotImplementedError()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands to a device."""
        assert self.hass is not None
        await self.hass.async_add_executor_job(
            ft.partial(self.send_command, command, **kwargs)
        )

    def learn_command(self, **kwargs: Any) -> None:
        """Learn a command from a device."""
        raise NotImplementedError()

    async def async_learn_command(self, **kwargs: Any) -> None:
        """Learn a command from a device."""
        assert self.hass is not None
        await self.hass.async_add_executor_job(ft.partial(self.learn_command, **kwargs))
