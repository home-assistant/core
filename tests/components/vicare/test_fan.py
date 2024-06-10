"""Test ViCare fan."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError


async def test_fan(
    hass: HomeAssistant,
    mock_vicare_fan: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the ViCare fan."""

    assert hass.states.get("fan.model0_ventilation") == snapshot


async def test_fan_turn_off(
    hass: HomeAssistant,
    mock_vicare_fan: MagicMock,
) -> None:
    """Verify turn_off works properly."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: ["fan.model0_ventilation"], ATTR_PERCENTAGE: 0},
            blocking=True,
        )
