"""Test the Tessie number platform."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import assert_entities, setup_platform


async def test_numbers(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the number entities are correct."""

    entry = await setup_platform(hass, [Platform.NUMBER])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

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
