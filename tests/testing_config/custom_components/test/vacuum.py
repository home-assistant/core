"""Provide a mock vacuum platform.

Call init before using it in your tests to ensure clean test data.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant

from tests.common import MockEntity

ENTITIES = []


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES
    ENTITIES = [] if empty else [MockVacuum()]


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)


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
