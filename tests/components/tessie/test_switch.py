"""Test the Tessie switch platform."""
from unittest.mock import patch

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.tessie.switch import DESCRIPTIONS
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant

from .common import TEST_VEHICLE_STATE_ONLINE, setup_platform


async def test_switches(hass: HomeAssistant) -> None:
    """Tests that the switches are correct."""

    assert len(hass.states.async_all("switch")) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all("switch")) == len(DESCRIPTIONS)

    assert (hass.states.get("switch.test_charge").state == STATE_ON) == (
        TEST_VEHICLE_STATE_ONLINE["charge_state"]["charge_enable_request"]
    )
    assert (hass.states.get("switch.test_sentry_mode").state == STATE_ON) == (
        TEST_VEHICLE_STATE_ONLINE["vehicle_state"]["sentry_mode"]
    )

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
