"""Switch support for the Skybell HD Doorbell."""
from __future__ import annotations

from typing import Any, cast

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SkybellEntity

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="do_not_disturb",
        name="Do Not Disturb",
    ),
    SwitchEntityDescription(
        key="do_not_ring",
        name="Do Not Ring",
    ),
    SwitchEntityDescription(
        key="motion_sensor",
        name="Motion Sensor",
    ),
)

# Deprecated in Home Assistant 2022.6
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ENTITY_NAMESPACE, default=DOMAIN): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SWITCH_TYPES)]
        ),
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the SkyBell switch."""
    async_add_entities(
        SkybellSwitch(coordinator, description)
        for coordinator in hass.data[DOMAIN][entry.entry_id]
        for description in SWITCH_TYPES
    )


class SkybellSwitch(SkybellEntity, SwitchEntity):
    """A switch implementation for Skybell devices."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._device.async_set_setting(self.entity_description.key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._device.async_set_setting(self.entity_description.key, False)

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        return cast(bool, getattr(self._device, self.entity_description.key))
