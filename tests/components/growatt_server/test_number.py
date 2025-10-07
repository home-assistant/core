"""Tests for the Growatt Server number platform."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

from growattServer import GrowattV1ApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import STATE_UNKNOWN, EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def number_only() -> AsyncGenerator[None]:
    """Enable only the number platform."""
    with patch(
        "homeassistant.components.growatt_server.PLATFORMS",
        [Platform.NUMBER],
    ):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that number entities are created for MIN devices."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_entity_values(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that number entities have correct values."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check entity values
    charge_power_state = hass.states.get("number.min123456_battery_charge_power_limit")
    assert charge_power_state is not None
    assert float(charge_power_state.state) == 50.0

    charge_soc_state = hass.states.get("number.min123456_battery_charge_soc_limit")
    assert charge_soc_state is not None
    assert float(charge_soc_state.state) == 10.0

    discharge_power_state = hass.states.get(
        "number.min123456_battery_discharge_power_limit"
    )
    assert discharge_power_state is not None
    assert float(discharge_power_state.state) == 80.0

    discharge_soc_state = hass.states.get(
        "number.min123456_battery_discharge_soc_limit"
    )
    assert discharge_soc_state is not None
    assert float(discharge_soc_state.state) == 20.0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_number_value_success(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting a number entity value successfully."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            "entity_id": "number.min123456_battery_charge_power_limit",
            ATTR_VALUE: 75,
        },
        blocking=True,
    )

    # Verify API was called with correct parameters
    mock_growatt_api.min_write_parameter.assert_called_once_with(
        "MIN123456", "charge_power", 75
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_number_value_api_error(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test handling API error when setting number value."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Mock API to raise error
    mock_growatt_api.min_write_parameter.side_effect = GrowattV1ApiError("API Error")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                "entity_id": "number.min123456_battery_charge_power_limit",
                ATTR_VALUE: 75,
            },
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_entity_attributes(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number entity attributes."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check entity registry attributes
    entity_entry = entity_registry.async_get(
        "number.min123456_battery_charge_power_limit"
    )
    assert entity_entry is not None
    assert entity_entry.entity_category == EntityCategory.CONFIG
    assert entity_entry.unique_id == "MIN123456_battery_charge_power_limit"

    # Check state attributes
    state = hass.states.get("number.min123456_battery_charge_power_limit")
    assert state is not None
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 100
    assert state.attributes["step"] == 1
    assert state.attributes["unit_of_measurement"] == "%"
    assert state.attributes["friendly_name"] == "MIN123456 Battery charge power limit"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_number_entities_service_calls(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service calls work for all number entities."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Test all four number entities
    test_cases = [
        ("number.min123456_battery_charge_power_limit", "charge_power", 75),
        ("number.min123456_battery_charge_soc_limit", "charge_stop_soc", 85),
        ("number.min123456_battery_discharge_power_limit", "discharge_power", 90),
        ("number.min123456_battery_discharge_soc_limit", "discharge_stop_soc", 25),
    ]

    for entity_id, expected_write_key, test_value in test_cases:
        mock_growatt_api.reset_mock()

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {"entity_id": entity_id, ATTR_VALUE: test_value},
            blocking=True,
        )

        # Verify API was called with correct parameters
        mock_growatt_api.min_write_parameter.assert_called_once_with(
            "MIN123456", expected_write_key, test_value
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_boundary_values(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting boundary values for number entities."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Test minimum value
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": "number.min123456_battery_charge_power_limit", ATTR_VALUE: 0},
        blocking=True,
    )

    mock_growatt_api.min_write_parameter.assert_called_with(
        "MIN123456", "charge_power", 0
    )

    # Test maximum value
    mock_growatt_api.reset_mock()
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": "number.min123456_battery_charge_power_limit", ATTR_VALUE: 100},
        blocking=True,
    )

    mock_growatt_api.min_write_parameter.assert_called_with(
        "MIN123456", "charge_power", 100
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_missing_data(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test number entity when coordinator data is missing."""
    # Set up API with missing data for one entity
    mock_growatt_api.min_detail.return_value = {
        "deviceSn": "MIN123456",
        # Missing 'chargePowerCommand' key to test None case
        "wchargeSOCLowLimit": 10,
        "disChargePowerCommand": 80,
        "wdisChargeSOCLowLimit": 20,
    }

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entity should exist but have unknown state due to missing data
    state = hass.states.get("number.min123456_battery_charge_power_limit")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_number_entities_for_non_min_devices(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that number entities are not created for non-MIN devices."""
    # Mock a different device type (not MIN)
    mock_get_device_list.return_value = (
        [{"deviceSn": "TLX123456", "deviceType": "tlx"}],
        "12345",
    )

    # Mock TLX API response to prevent coordinator errors
    mock_growatt_api.tlx_detail.return_value = {"data": {}}

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Should have no number entities for TLX devices
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    number_entities = [entry for entry in entity_entries if entry.domain == "number"]
    assert len(number_entities) == 0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_float_to_int_conversion(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that float values are converted to integers when setting."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Test setting a float value gets converted to int
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": "number.min123456_battery_charge_power_limit", ATTR_VALUE: 75.7},
        blocking=True,
    )

    # Verify API was called with integer value
    mock_growatt_api.min_write_parameter.assert_called_once_with(
        "MIN123456",
        "charge_power",
        75,  # Should be converted to int
    )
