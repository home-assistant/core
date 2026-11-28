"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from pytest_homeassistant.common import MockEntity

from homeassistant.components.fan import (
    DOMAIN,
    FanEntity,
    FanService,
    FanServiceArgument,
)
from homeassistant.const import ENTITY_MATCH_ALL, TargetKey
from homeassistant.core import HomeAssistant


async def async_turn_on(
    hass: HomeAssistant,
    entity_id=ENTITY_MATCH_ALL,
    percentage: int | None = None,
    preset_mode: str | None = None,
) -> None:
    """Turn all or specified fan on."""
    data = {
        key: value
        for key, value in (
            (TargetKey.ENTITY_ID, entity_id),
            (FanServiceArgument.PERCENTAGE, percentage),
            (FanServiceArgument.PRESET_MODE, preset_mode),
        )
        if value is not None
    }

    await hass.services.async_call(DOMAIN, FanService.TURN_ON, data, blocking=True)
    await hass.async_block_till_done()


async def async_turn_off(hass: HomeAssistant, entity_id=ENTITY_MATCH_ALL) -> None:
    """Turn all or specified fan off."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(DOMAIN, FanService.TURN_OFF, data, blocking=True)
    await hass.async_block_till_done()


async def async_oscillate(
    hass: HomeAssistant, entity_id=ENTITY_MATCH_ALL, should_oscillate: bool = True
) -> None:
    """Set oscillation on all or specified fan."""
    data = {
        key: value
        for key, value in (
            (TargetKey.ENTITY_ID, entity_id),
            (FanServiceArgument.OSCILLATING, should_oscillate),
        )
        if value is not None
    }

    await hass.services.async_call(DOMAIN, FanService.OSCILLATE, data, blocking=True)
    await hass.async_block_till_done()


async def async_set_preset_mode(
    hass: HomeAssistant, entity_id=ENTITY_MATCH_ALL, preset_mode: str | None = None
) -> None:
    """Set preset mode for all or specified fan."""
    data = {
        key: value
        for key, value in (
            (TargetKey.ENTITY_ID, entity_id),
            (FanServiceArgument.PRESET_MODE, preset_mode),
        )
        if value is not None
    }

    await hass.services.async_call(
        DOMAIN, FanService.SET_PRESET_MODE, data, blocking=True
    )
    await hass.async_block_till_done()


async def async_set_percentage(
    hass: HomeAssistant, entity_id=ENTITY_MATCH_ALL, percentage: int | None = None
) -> None:
    """Set percentage for all or specified fan."""
    data = {
        key: value
        for key, value in (
            (TargetKey.ENTITY_ID, entity_id),
            (FanServiceArgument.PERCENTAGE, percentage),
        )
        if value is not None
    }

    await hass.services.async_call(
        DOMAIN, FanService.SET_PERCENTAGE, data, blocking=True
    )
    await hass.async_block_till_done()


async def async_increase_speed(
    hass: HomeAssistant, entity_id=ENTITY_MATCH_ALL, percentage_step: int | None = None
) -> None:
    """Increase speed for all or specified fan."""
    data = {
        key: value
        for key, value in (
            (TargetKey.ENTITY_ID, entity_id),
            (FanServiceArgument.PERCENTAGE_STEP, percentage_step),
        )
        if value is not None
    }

    await hass.services.async_call(
        DOMAIN, FanService.INCREASE_SPEED, data, blocking=True
    )
    await hass.async_block_till_done()


async def async_decrease_speed(
    hass: HomeAssistant, entity_id=ENTITY_MATCH_ALL, percentage_step: int | None = None
) -> None:
    """Decrease speed for all or specified fan."""
    data = {
        key: value
        for key, value in (
            (TargetKey.ENTITY_ID, entity_id),
            (FanServiceArgument.PERCENTAGE_STEP, percentage_step),
        )
        if value is not None
    }

    await hass.services.async_call(
        DOMAIN, FanService.DECREASE_SPEED, data, blocking=True
    )
    await hass.async_block_till_done()


async def async_set_direction(
    hass: HomeAssistant, entity_id=ENTITY_MATCH_ALL, direction: str | None = None
) -> None:
    """Set direction for all or specified fan."""
    data = {
        key: value
        for key, value in (
            (TargetKey.ENTITY_ID, entity_id),
            (FanServiceArgument.DIRECTION, direction),
        )
        if value is not None
    }

    await hass.services.async_call(
        DOMAIN, FanService.SET_DIRECTION, data, blocking=True
    )
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
