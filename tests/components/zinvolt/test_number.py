"""Tests for the Zinvolt number."""

import json
from unittest.mock import AsyncMock, patch

from pytest_homeassistant.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from zinvolt.models import BatteryState

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.zinvolt.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_zinvolt_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.zinvolt._PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_max_output_when_unlocked(
    hass: HomeAssistant,
    mock_zinvolt_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test max_output value stays within its own bound once output is unlocked."""
    fixture_data = await async_load_json_object_fixture(
        hass, "current_state.json", DOMAIN
    )
    fixture_data["globalSettings"]["maxOutputUnlocked"] = True
    mock_zinvolt_client.get_battery_status.return_value = BatteryState.from_json(
        json.dumps(fixture_data)
    )

    with patch("homeassistant.components.zinvolt._PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.zinvolt_batterij_maximum_output")
    assert state.state == "2000"
    assert state.attributes["max"] == 2000


async def test_set_max_charge_power(
    hass: HomeAssistant,
    mock_zinvolt_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the maximum charge power."""
    await setup_integration(hass, mock_config_entry)

    mock_zinvolt_client.get_battery_status.return_value.global_settings.maximum_charge_power = 1500

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.zinvolt_batterij_maximum_charge_power",
            ATTR_VALUE: 1500,
        },
        blocking=True,
    )

    mock_zinvolt_client.set_max_charge_power.assert_called_once_with(
        "a125ef17-6bdf-45ad-b106-ce54e95e4634", 1500
    )
    assert (
        hass.states.get("number.zinvolt_batterij_maximum_charge_power").state == "1500"
    )
