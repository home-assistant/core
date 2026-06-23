"""Test Grandstream sensor platform."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_gds_api")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_unavailable_mapping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gds_api,
) -> None:
    """Test sensor maps unavailable to no_available_account."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
        return_value={"phone_status": "unavailable"},
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.entry_gds3710_ec74d79753c5_device_status")
    assert state is not None
    assert state.state == "no_available_account"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_unknown_returns_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gds_api,
) -> None:
    """Test sensor returns None for unknown state."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
        return_value={"phone_status": "unknown"},
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.entry_gds3710_ec74d79753c5_device_status")
    assert state is not None
    assert state.state == "unknown"
