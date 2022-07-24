"""Support for lawn mower robots."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum
from functools import partial
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # noqa: F401 # STATE_PAUSED/IDLE are API
    ATTR_BATTERY_LEVEL,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_IDLE,
    STATE_ON,
    STATE_PAUSED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    make_entity_service_schema,
)
from homeassistant.helpers.entity import (
    Entity,
    EntityDescription,
    ToggleEntityDescription,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

DOMAIN = "lawn_mower"
ENTITY_ID_FORMAT = DOMAIN + ".{}"
SCAN_INTERVAL = timedelta(seconds=20)

ATTR_BATTERY_ICON = "battery_icon"
ATTR_STATUS = "status"

SERVICE_PAUSE = "pause"
SERVICE_RETURN_TO_BASE = "return_to_base"
SERVICE_START_PAUSE = "start_pause"
SERVICE_START = "start"
SERVICE_STOP = "stop"

STATE_DOCKED = "docked"
STATE_ERROR = "error"
STATE_MOWING = "mowing"
STATE_RETURNING = "returning"

STATES = [STATE_DOCKED, STATE_ERROR, STATE_MOWING, STATE_RETURNING]

DEFAULT_NAME = "Lawn mower robot"


class LawnMowerEntityFeature(IntEnum):
    """Supported features of the lawn_mower entity."""

    TURN_ON = 1
    TURN_OFF = 2
    PAUSE = 4
    STOP = 8
    RETURN_HOME = 16
    BATTERY = 32
    STATUS = 64
    STATE = 128
    START = 256


@bind_hass
def is_on(hass, entity_id):
    """Return if the lawn mower is on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the lawn_mower component."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(SERVICE_TURN_ON, {}, "async_turn_on")
    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")
    component.async_register_entity_service(SERVICE_TOGGLE, {}, "async_toggle")
    component.async_register_entity_service(
        SERVICE_START_PAUSE, {}, "async_start_pause"
    )
    component.async_register_entity_service(SERVICE_START, {}, "async_start")
    component.async_register_entity_service(SERVICE_PAUSE, {}, "async_pause")
    component.async_register_entity_service(
        SERVICE_RETURN_TO_BASE, {}, "async_return_to_base"
    )
    component.async_register_entity_service(SERVICE_STOP, {}, "async_stop")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class _BaseLawnMower(Entity):
    """Representation of a base lawn_mower.

    Contains common properties and functions for all lawn mower devices.
    """

    _attr_battery_icon: str
    _attr_battery_level: int | None = None
    _attr_supported_features: int

    @property
    def supported_features(self) -> int:
        """Flag lawn mower features that are supported."""
        return self._attr_supported_features

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the lawn mower."""
        return self._attr_battery_level

    @property
    def battery_icon(self) -> str:
        """Return the battery icon for the lawn mower."""
        return self._attr_battery_icon

    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the lawn mower."""
        data: dict[str, Any] = {}

        if self.supported_features & LawnMowerEntityFeature.BATTERY:
            data[ATTR_BATTERY_LEVEL] = self.battery_level
            data[ATTR_BATTERY_ICON] = self.battery_icon

        return data

    def stop(self, **kwargs: Any) -> None:
        """Stop the lawn mower."""
        raise NotImplementedError()

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the lawn mower.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.stop, **kwargs))

    def return_to_base(self, **kwargs: Any) -> None:
        """Set the lawn mower to return to the dock."""
        raise NotImplementedError()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the lawn mower to return to the dock.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.return_to_base, **kwargs))


@dataclass
class LawnMowerEntityDescription(ToggleEntityDescription):
    """A class that describes lawn_mower entities."""


@dataclass
class StateLawnMowerEntityDescription(EntityDescription):
    """A class that describes lawn_mower entities."""


class StateLawnMowerEntity(_BaseLawnMower):
    """Representation of a lawn mower robot that supports states."""

    entity_description: StateLawnMowerEntityDescription

    @property
    def state(self) -> str | None:
        """Return the state of the lawn mower."""
        return None

    @property
    def battery_icon(self) -> str:
        """Return the battery icon for the lawn mower."""
        charging = bool(self.state == STATE_DOCKED)

        return icon_for_battery_level(
            battery_level=self.battery_level, charging=charging
        )

    def start(self) -> None:
        """Start or resume the mowing task."""
        raise NotImplementedError()

    async def async_start(self) -> None:
        """Start or resume the mowing task.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(self.start)

    def pause(self) -> None:
        """Pause the mowing task."""
        raise NotImplementedError()

    async def async_pause(self) -> None:
        """Pause the mowing task.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(self.pause)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Not supported."""

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Not supported."""

    async def async_toggle(self, **kwargs: Any) -> None:
        """Not supported."""
