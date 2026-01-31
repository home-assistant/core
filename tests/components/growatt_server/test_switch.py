"""Tests for the Growatt Server switch platform."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from growattServer import GrowattV1ApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.growatt_server.coordinator import SCAN_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

DOMAIN = "growatt_server"


@pytest.fixture(autouse=True)
async def switch_only() -> AsyncGenerator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.growatt_server.PLATFORMS",
        [Platform.SWITCH],
    ):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_switch_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that switch entities are created for MIN devices."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    ("service", "expected_value"),
    [
        (SERVICE_TURN_ON, 1),
        (SERVICE_TURN_OFF, 0),
    ],
)
async def test_switch_service_call_success(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    service: str,
    expected_value: int,
) -> None:
    """Test switch service calls successfully."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "switch.min123456_charge_from_grid"},
        blocking=True,
    )

    # Verify API was called with correct parameters
    mock_growatt_v1_api.min_write_parameter.assert_called_once_with(
        "MIN123456", "ac_charge", expected_value
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    "service",
    [SERVICE_TURN_ON, SERVICE_TURN_OFF],
)
async def test_switch_service_call_api_error(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    service: str,
) -> None:
    """Test handling API error when calling switch services."""
    # Mock API to raise error
    mock_growatt_v1_api.min_write_parameter.side_effect = GrowattV1ApiError("API Error")

    with pytest.raises(HomeAssistantError, match="Error while setting switch state"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {"entity_id": "switch.min123456_charge_from_grid"},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_state_handling_integer_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_v1_api,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switch state handling with integer values from API."""
    # Set up integration
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Should interpret 1 as ON (from default mock data)
    state = hass.states.get("switch.min123456_charge_from_grid")
    assert state is not None
    assert state.state == STATE_ON

    # Test with 0 integer value
    mock_growatt_v1_api.min_detail.return_value = {
        "deviceSn": "MIN123456",
        "acChargeEnable": 0,  # Integer value
    }

    # Advance time to trigger coordinator refresh
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Should interpret 0 as OFF
    state = hass.states.get("switch.min123456_charge_from_grid")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_missing_data(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch entity when coordinator data is missing."""
    # Set up API with missing data for switch entity
    mock_growatt_v1_api.min_detail.return_value = {
        "deviceSn": "MIN123456",
        # Missing 'acChargeEnable' key to test None case
    }

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entity should exist but have unknown state due to missing data
    state = hass.states.get("switch.min123456_charge_from_grid")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_switch_entities_for_non_min_devices(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that switch entities are not created for non-MIN devices."""
    # Mock a different device type (not MIN) - type 7 is MIN, type 8 is non-MIN
    mock_growatt_v1_api.device_list.return_value = {
        "devices": [
            {
                "device_sn": "TLX123456",
                "type": 8,  # Non-MIN device type (MIN is type 7)
            }
        ]
    }

    # Mock TLX API response to prevent coordinator errors
    mock_growatt_v1_api.tlx_detail.return_value = {"data": {}}

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Should have no switch entities for TLX devices
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    switch_entities = [entry for entry in entity_entries if entry.domain == "switch"]
    assert len(switch_entities) == 0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_switch_entities_for_classic_api(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that switch entities are not created for Classic API."""
    # Mock device list to return no devices
    mock_growatt_classic_api.device_list.return_value = []

    mock_config_entry_classic.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry_classic.entry_id)
    await hass.async_block_till_done()

    # Should have no switch entities for classic API (no devices)
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry_classic.entry_id
    )
    switch_entities = [entry for entry in entity_entries if entry.domain == "switch"]
    assert len(switch_entities) == 0
