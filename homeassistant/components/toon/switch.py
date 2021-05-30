"""Support for Toon switches."""
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

from .const import (
    ATTR_DEFAULT_ENABLED,
    ATTR_ICON,
    ATTR_INVERTED,
    ATTR_MEASUREMENT,
    ATTR_NAME,
    ATTR_SECTION,
    DOMAIN,
    SWITCH_ENTITIES,
)
from .coordinator import ToonDataUpdateCoordinator
from .helpers import toon_exception_handler
from .models import ToonDisplayDeviceEntity, ToonEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up a Toon switches based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [ToonProgramSwitch(coordinator), ToonHolidayModeSwitch(coordinator)]
    )


class ToonSwitch(ToonEntity, SwitchEntity):
    """Defines an Toon switch."""

    def __init__(self, coordinator: ToonDataUpdateCoordinator, *, key: str) -> None:
        """Initialize the Toon switch."""
        self.key = key

        super().__init__(
            coordinator,
            enabled_default=SWITCH_ENTITIES[key][ATTR_DEFAULT_ENABLED],
            icon=SWITCH_ENTITIES[key][ATTR_ICON],
            name=SWITCH_ENTITIES[key][ATTR_NAME],
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this binary sensor."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return f"{agreement_id}_{self.key}"

    @property
    def is_on(self) -> bool:
        """Return the status of the binary sensor."""
        section = getattr(
            self.coordinator.data, SWITCH_ENTITIES[self.key][ATTR_SECTION]
        )
        value = getattr(section, SWITCH_ENTITIES[self.key][ATTR_MEASUREMENT])

        if SWITCH_ENTITIES[self.key][ATTR_INVERTED]:
            return not value

        return value


class ToonProgramSwitch(ToonSwitch, ToonDisplayDeviceEntity):
    """Defines a Toon program switch."""

    def __init__(self, coordinator: ToonDataUpdateCoordinator) -> None:
        """Initialize the Toon program switch."""
        super().__init__(coordinator, key="thermostat_program")

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

    def __init__(self, coordinator: ToonDataUpdateCoordinator) -> None:
        """Initialize the Toon holiday switch."""
        super().__init__(coordinator, key="thermostat_holiday_mode")

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
