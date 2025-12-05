"""Helper utilities for Sure Petcare tests."""

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def call_switch_turn_on(hass: HomeAssistant, entity_id: str) -> None:
    """Call the switch.turn_on service."""
    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )


async def call_switch_turn_off(hass: HomeAssistant, entity_id: str) -> None:
    """Call the switch.turn_off service."""
    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
