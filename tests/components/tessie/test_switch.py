"""Test the Tessie switch platform."""
from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_switches(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Tests that the switche entities are correct."""

    assert len(hass.states.async_all(SWITCH_DOMAIN)) == 0

    await setup_platform(hass)

    assert hass.states.async_all(SWITCH_DOMAIN) == snapshot(name="all")

    entity_id = "switch.test_charge"
    with patch(
        "homeassistant.components.tessie.switch.start_charging",
    ) as mock_start_charging:
        # Test Switch On
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_start_charging.assert_called_once()
    assert hass.states.get(entity_id) == snapshot(name=SERVICE_TURN_ON)

    with patch(
        "homeassistant.components.tessie.switch.stop_charging",
    ) as mock_stop_charging:
        # Test Switch Off
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_stop_charging.assert_called_once()

    assert hass.states.get(entity_id) == snapshot(name=SERVICE_TURN_OFF)
