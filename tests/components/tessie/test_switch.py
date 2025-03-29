"""Test the Tessie switch platform."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import RESPONSE_OK, assert_entities, setup_platform


async def test_switches(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the switch entities are correct."""

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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("name", "on", "off"),
    [
        (
            "energy_site_storm_watch",
            "storm_mode",
            "storm_mode",
        ),
        (
            "energy_site_allow_charging_from_grid",
            "grid_import_export",
            "grid_import_export",
        ),
    ],
)
async def test_switch_services(
    hass: HomeAssistant, name: str, on: str, off: str
) -> None:
    """Tests that the switch service calls work."""

    await setup_platform(hass, [Platform.SWITCH])

    entity_id = f"switch.{name}"
    with patch(
        f"tesla_fleet_api.tessie.EnergySite.{on}",
        return_value=RESPONSE_OK,
    ) as call:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == STATE_ON
        call.assert_called_once()

    with patch(
        f"tesla_fleet_api.tessie.EnergySite.{off}",
        return_value=RESPONSE_OK,
    ) as call:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF
        call.assert_called_once()
