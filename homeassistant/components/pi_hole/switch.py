"""Support for turning on and off Pi-hole system."""
from __future__ import annotations

import logging
from typing import Any

from hole.exceptions import HoleError
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PiHoleEntity
from .const import (
    DATA_KEY_API,
    DATA_KEY_COORDINATOR,
    DOMAIN as PIHOLE_DOMAIN,
    SERVICE_DISABLE,
    SERVICE_DISABLE_ATTR_DURATION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Pi-hole switch."""
    name = entry.data[CONF_NAME]
    hole_data = hass.data[PIHOLE_DOMAIN][entry.entry_id]
    switches = [
        PiHoleSwitch(
            hole_data[DATA_KEY_API],
            hole_data[DATA_KEY_COORDINATOR],
            name,
            entry.entry_id,
        )
    ]
    async_add_entities(switches, True)

    # register service
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_DISABLE,
        {
            vol.Required(SERVICE_DISABLE_ATTR_DURATION): vol.All(
                cv.time_period_str, cv.positive_timedelta
            ),
        },
        "async_disable",
    )


class PiHoleSwitch(PiHoleEntity, SwitchEntity):
    """Representation of a Pi-hole switch."""

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique id of the switch."""
        return f"{self._server_unique_id}/Switch"

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return "mdi:pi-hole"

    @property
    def is_on(self) -> bool:
        """Return if the service is on."""
        return self.api.data.get("status") == "enabled"  # type: ignore[no-any-return]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the service."""
        try:
            await self.api.enable()
            await self.async_update()
        except HoleError as err:
            _LOGGER.error("Unable to enable Pi-hole: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the service."""
        await self.async_disable()

    async def async_disable(self, duration: Any = None) -> None:
        """Disable the service for a given duration."""
        duration_seconds = True  # Disable infinitely by default
        if duration is not None:
            duration_seconds = duration.total_seconds()
            _LOGGER.debug(
                "Disabling Pi-hole '%s' (%s) for %d seconds",
                self.name,
                self.api.host,
                duration_seconds,
            )
        try:
            await self.api.disable(duration_seconds)
            await self.async_update()
        except HoleError as err:
            _LOGGER.error("Unable to disable Pi-hole: %s", err)
