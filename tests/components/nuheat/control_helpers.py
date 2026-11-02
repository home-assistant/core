"""Synthetic climate command and clock helpers."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.climate import HVACMode
from homeassistant.components.nuheat.climate import NuHeatClimateEntity
from homeassistant.components.nuheat.const import (
    PRESET_PERMANENT_HOLD,
    PRESET_RUN,
    PRESET_TEMPORARY_HOLD,
)
from homeassistant.core import HomeAssistant

CONTROLS = ["run", "temporary", "permanent", "heat", "auto", "off", "on"]


async def advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    """Deliver scheduled callbacks using the synthetic clock."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def command(entity: NuHeatClimateEntity, control: str) -> None:
    """Dispatch an existing climate control without contacting the cloud."""
    if control in ("run", "temporary", "permanent"):
        await entity.async_set_preset_mode(
            {
                "run": PRESET_RUN,
                "temporary": PRESET_TEMPORARY_HOLD,
                "permanent": PRESET_PERMANENT_HOLD,
            }[control]
        )
    elif control in ("heat", "auto"):
        await entity.async_set_hvac_mode(
            {"heat": HVACMode.HEAT, "auto": HVACMode.AUTO}[control]
        )
    elif control == "off":
        await entity.async_turn_off()
    else:
        await entity.async_turn_on()
