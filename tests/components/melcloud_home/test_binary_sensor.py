"""Tests for the MELCloud Home binary sensor platform."""

from unittest.mock import AsyncMock, patch

from aiomelcloudhome import UserContext
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.melcloud_home.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    snapshot_platform,
)

ATA_ERROR_ENTITY_ID = "binary_sensor.living_room_ac_error"


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.melcloud_home.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("holiday_mode", "expected_state"),
    [
        pytest.param({"enabled": True, "active": False}, STATE_OFF, id="scheduled"),
        pytest.param({"enabled": True, "active": True}, STATE_ON, id="active"),
    ],
)
async def test_holiday_mode_active(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    holiday_mode: dict[str, bool],
    expected_state: str,
) -> None:
    """Test the holiday mode sensor is only on while the holiday is running."""
    context = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    context["buildings"][0]["airToAirUnits"][0]["holidayMode"] = {
        **holiday_mode,
        "startDate": "2026-06-01T00:00:00",
        "endDate": "2026-06-14T00:00:00",
    }
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(context)

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("binary_sensor.living_room_ac_holiday_mode"))
    assert state.state == expected_state
