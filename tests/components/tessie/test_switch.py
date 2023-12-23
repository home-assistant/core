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

    with patch(
        "homeassistant.components.tessie.entity.TessieEntity.run",
        return_value=True,
    ) as mock_run:
        # Test Switch On
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ["switch.test_charge"]},
            blocking=True,
        )
        mock_run.assert_called_once()
        mock_run.reset_mock()

        # Test Switch Off
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ["switch.test_charge"]},
            blocking=True,
        )
        mock_run.assert_called_once()
    assert hass.states.get("switch.test_charge") == snapshot
