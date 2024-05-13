"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    ATTR_PRESET_MODE,
    DOMAIN,
    SERVICE_DECREASE_SPEED,
    SERVICE_INCREASE_SPEED,
    SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    FanEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)

from tests.common import MockEntity


async def async_turn_on(
    hass,
    entity_id=ENTITY_MATCH_ALL,
    percentage: int | None = None,
    preset_mode: str | None = None,
) -> None:
    """Turn all or specified fan on."""
    data = {
        key: value
        for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_PERCENTAGE, percentage),
            (ATTR_PRESET_MODE, preset_mode),
        ]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data, blocking=True)
    await hass.async_block_till_done()


async def async_turn_off(hass, entity_id=ENTITY_MATCH_ALL) -> None:
    """Turn all or specified fan off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data, blocking=True)
    await hass.async_block_till_done()


async def async_oscillate(
    hass, entity_id=ENTITY_MATCH_ALL, should_oscillate: bool = True
) -> None:
    """Set oscillation on all or specified fan."""
    data = {
        key: value
        for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_OSCILLATING, should_oscillate),
        ]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_OSCILLATE, data, blocking=True)
    await hass.async_block_till_done()


async def async_set_preset_mode(
    hass, entity_id=ENTITY_MATCH_ALL, preset_mode: str | None = None
) -> None:
    """Set preset mode for all or specified fan."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_PRESET_MODE, preset_mode)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_SET_PRESET_MODE, data, blocking=True)
    await hass.async_block_till_done()


async def async_set_percentage(
    hass, entity_id=ENTITY_MATCH_ALL, percentage: int | None = None
) -> None:
    """Set percentage for all or specified fan."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_PERCENTAGE, percentage)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_SET_PERCENTAGE, data, blocking=True)
    await hass.async_block_till_done()


async def async_increase_speed(
    hass, entity_id=ENTITY_MATCH_ALL, percentage_step: int | None = None
) -> None:
    """Increase speed for all or specified fan."""
    data = {
        key: value
        for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_PERCENTAGE_STEP, percentage_step),
        ]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_INCREASE_SPEED, data, blocking=True)
    await hass.async_block_till_done()


async def async_decrease_speed(
    hass, entity_id=ENTITY_MATCH_ALL, percentage_step: int | None = None
) -> None:
    """Decrease speed for all or specified fan."""
    data = {
        key: value
        for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_PERCENTAGE_STEP, percentage_step),
        ]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_DECREASE_SPEED, data, blocking=True)
    await hass.async_block_till_done()


async def async_set_direction(
    hass, entity_id=ENTITY_MATCH_ALL, direction: str | None = None
) -> None:
    """Set direction for all or specified fan."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_DIRECTION, direction)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_SET_DIRECTION, data, blocking=True)
    await hass.async_block_till_done()


class MockFan(MockEntity, FanEntity):
    """Mock Fan class."""

    @property
    def preset_modes(self) -> list[str] | None:
        """Return preset mode."""
        return self._handle("preset_modes")

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        self._attr_preset_mode = preset_mode
