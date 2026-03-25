"""Switch support for the Skybell HD Doorbell."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import SkybellEntity

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="do_not_disturb",
        translation_key="do_not_disturb",
    ),
    SwitchEntityDescription(
        key="do_not_ring",
        translation_key="do_not_ring",
    ),
    SwitchEntityDescription(
        key="motion_sensor",
        translation_key="motion_sensor",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
