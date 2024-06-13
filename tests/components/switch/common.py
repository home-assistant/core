"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from typing import Any

from homeassistant.components.switch import DOMAIN, SwitchDeviceClass, SwitchEntity
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.loader import bind_hass


@bind_hass
def turn_on(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified switch on."""
    hass.add_job(async_turn_on, hass, entity_id)


async def async_turn_on(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified switch on."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data, blocking=True)


@bind_hass
def turn_off(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified switch off."""
    hass.add_job(async_turn_off, hass, entity_id)


async def async_turn_off(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified switch off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data, blocking=True)


class MockSwitch(SwitchEntity):
    """Mocked switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, name: str | None, state: str) -> None:
        """Initialize the mock switch entity."""
        self._attr_name = name
        self._attr_is_on = state == STATE_ON

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._attr_is_on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_is_on = False


def get_mock_switch_entities() -> list[MockSwitch]:
    """Return a list of mock switch entities."""
    return [
        MockSwitch("AC", STATE_ON),
        MockSwitch("AC", STATE_OFF),
        MockSwitch(None, STATE_OFF),
    ]
