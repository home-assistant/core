"""Test ViCare fan."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.vicare.fan import ORDERED_NAMED_FAN_SPEEDS
from homeassistant.components.vicare.types import VentilationMode
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_fan_update(
    hass: HomeAssistant,
    mock_vicare_fan: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the ViCare fan."""

    await async_setup_component(hass, HA_DOMAIN, {})

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["fan.model0_ventilation"]},
        blocking=True,
    )

    assert hass.states.get("fan.model0_ventilation") == snapshot
    assert VentilationMode.PERMANENT == "permanent"
    assert "levelTwo" in ORDERED_NAMED_FAN_SPEEDS


@pytest.mark.parametrize(
    ("percentage", "expected_fan_mode"),
    [
        (100, "levelFour"),
    ],
)
async def test_fan_set_percentage(
    hass: HomeAssistant,
    mock_vicare_fan: MagicMock,
    percentage,
    snapshot: SnapshotAssertion,
    expected_fan_mode,
) -> None:
    """Verify set_percentage works properly through the entire range of FanModes."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ["fan.model0_ventilation"], ATTR_PERCENTAGE: percentage},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("fan.model0_ventilation") == snapshot
    # TODO: verify expected_fan_mode in MockService
