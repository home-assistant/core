"""Tests for the MELCloud Home sensor platform."""

from unittest.mock import AsyncMock, patch

from aiomelcloudhome import UserContext
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.melcloud_home.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    snapshot_platform,
)

OPERATION_STATUS_ENTITY_ID = "sensor.heat_pump_operation_status"


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.usefixtures("mock_melcloud_client")
@pytest.mark.freeze_time("2026-06-08 12:00:00+00:00")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.melcloud_home.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("operation_mode", "expected_state"),
    [
        pytest.param("Stop", "idle", id="idle"),
        pytest.param("HotWater", "heating_water", id="heating_water"),
        pytest.param("Heat", "heating_zones", id="heat"),
        pytest.param("HeatZones", "heating_zones", id="heating_zones"),
        pytest.param("Cool", "cooling", id="cooling"),
        pytest.param("Defrost", STATE_UNKNOWN, id="unsupported_mode"),
    ],
)
async def test_operation_status(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    operation_mode: str,
    expected_state: str,
) -> None:
    """Test the operation status follows the unit's operation mode."""
    context = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    settings = {
        unit_setting["name"]: unit_setting
        for unit_setting in context["buildings"][0]["airToWaterUnits"][0]["settings"]
    }
    settings["OperationMode"]["value"] = operation_mode
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(context)

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(OPERATION_STATUS_ENTITY_ID))
    assert state.state == expected_state
