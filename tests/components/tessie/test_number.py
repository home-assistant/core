"""Test the Tessie number platform."""
from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_numbers(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Tests that the number entities are correct."""

    assert len(hass.states.async_all("number")) == 0

    await setup_platform(hass)

    assert hass.states.async_all("number") == snapshot(name="all")

    # Test number set value functions
    entity_id = "number.test_charge_current"
    with patch(
        "homeassistant.components.tessie.number.set_charging_amps",
    ) as mock_set_charging_amps:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: [entity_id], "value": 16},
            blocking=True,
        )
        mock_set_charging_amps.assert_called_once()
    assert hass.states.get(entity_id).state == "16.0"

    entity_id = "number.test_charge_limit"
    with patch(
        "homeassistant.components.tessie.number.set_charge_limit",
    ) as mock_set_charge_limit:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: [entity_id], "value": 80},
            blocking=True,
        )
        mock_set_charge_limit.assert_called_once()
    assert hass.states.get(entity_id).state == "80.0"

    entity_id = "number.test_speed_limit"
    with patch(
        "homeassistant.components.tessie.number.set_speed_limit",
    ) as mock_set_speed_limit:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: [entity_id], "value": 60},
            blocking=True,
        )
        mock_set_speed_limit.assert_called_once()
    assert hass.states.get(entity_id).state == "60.0"
