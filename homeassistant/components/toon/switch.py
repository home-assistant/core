"""Support for Toon switches."""
from __future__ import annotations

from typing import Any

from toonapi import (
    ACTIVE_STATE_AWAY,
    ACTIVE_STATE_HOLIDAY,
    PROGRAM_STATE_OFF,
    PROGRAM_STATE_ON,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ToonDataUpdateCoordinator
from .helpers import toon_exception_handler
from .models import ToonDisplayDeviceEntity, ToonEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up a Toon switches based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [description.cls(coordinator, description) for description in SWITCH_ENTITIES]
    )


class ToonSwitch(ToonEntity, SwitchEntity):
    """Defines an Toon switch."""

    entity_description: ToonSwitchEntityDescription

    def __init__(
        self,
        coordinator: ToonDataUpdateCoordinator,
        description: ToonSwitchEntityDescription,
    ) -> None:
        """Initialize the Toon switch."""
        self.entity_description = description
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{coordinator.data.agreement.agreement_id}_{description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return the status of the binary sensor."""
        section = getattr(self.coordinator.data, self.entity_description.section)
        return getattr(section, self.entity_description.measurement)


class ToonProgramSwitch(ToonSwitch, ToonDisplayDeviceEntity):
    """Defines a Toon program switch."""

    @toon_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Toon program switch."""
        await self.coordinator.toon.set_active_state(
            ACTIVE_STATE_AWAY, PROGRAM_STATE_OFF
        )

    @toon_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Toon program switch."""
        await self.coordinator.toon.set_active_state(
            ACTIVE_STATE_AWAY, PROGRAM_STATE_ON
        )


class ToonHolidayModeSwitch(ToonSwitch, ToonDisplayDeviceEntity):
    """Defines a Toon Holiday mode switch."""

    @toon_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Toon holiday mode switch."""
        await self.coordinator.toon.set_active_state(
            ACTIVE_STATE_AWAY, PROGRAM_STATE_ON
        )

    @toon_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Toon holiday mode switch."""
        await self.coordinator.toon.set_active_state(
            ACTIVE_STATE_HOLIDAY, PROGRAM_STATE_OFF
        )


# pylint: disable=wrong-import-position
# Necessary to prevent circular import
from .entity_descriptions import (  # noqa: E402
    SWITCH_ENTITIES,
    ToonSwitchEntityDescription,
)
