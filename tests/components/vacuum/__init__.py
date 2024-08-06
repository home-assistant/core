"""The tests for vacuum platforms."""

from typing import Any

from homeassistant.components.vacuum import (
    DOMAIN,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockEntity


class MockVacuum(MockEntity, StateVacuumEntity):
    """Mock vacuum class."""

    _attr_supported_features = (
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.MAP
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
    )
    _attr_battery_level = 99
    _attr_fan_speed_list = ["slow", "fast"]

    def __init__(self, **values: Any) -> None:
        """Initialize a mock vacuum entity."""
        super().__init__(**values)
        self._attr_state = STATE_DOCKED
        self._attr_fan_speed = "slow"

    def stop(self, **kwargs: Any) -> None:
        """Stop cleaning."""
        self._attr_state = STATE_IDLE

    def return_to_base(self, **kwargs: Any) -> None:
        """Return to base."""
        self._attr_state = STATE_RETURNING

    def clean_spot(self, **kwargs: Any) -> None:
        """Clean a spot."""
        self._attr_state = STATE_CLEANING

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set the fan speed."""
        self._attr_fan_speed = fan_speed

    def start(self) -> None:
        """Start cleaning."""
        self._attr_state = STATE_CLEANING

    def pause(self) -> None:
        """Pause cleaning."""
        self._attr_state = STATE_PAUSED


async def help_async_setup_entry_init(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Set up test config entry."""
    await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
    return True


async def help_async_unload_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Unload test config emntry."""
    return await hass.config_entries.async_unload_platforms(
        config_entry, [Platform.VACUUM]
    )
