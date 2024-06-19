"""Test the Tessie switch platform."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import assert_entities, setup_platform


async def test_switches(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the switche entities are correct."""

    entry = await setup_platform(hass, [Platform.SWITCH])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

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
