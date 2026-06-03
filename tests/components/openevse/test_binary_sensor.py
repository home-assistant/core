"""Tests for the OpenEVSE binary sensor platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test the binary sensor entities."""
    with patch("homeassistant.components.openevse.PLATFORMS", [Platform.BINARY_SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_disabled_by_default_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test the disabled by default binary sensor entities."""
    with patch("homeassistant.components.openevse.PLATFORMS", [Platform.BINARY_SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    state = hass.states.get("binary_sensor.openevse_mock_config_ethernet_connected")
    assert state is None

    entry = entity_registry.async_get(
        "binary_sensor.openevse_mock_config_ethernet_connected"
    )
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    state = hass.states.get("binary_sensor.openevse_mock_config_limit_active")
    assert state is None

    entry = entity_registry.async_get("binary_sensor.openevse_mock_config_limit_active")
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    state = hass.states.get("binary_sensor.openevse_mock_config_mqtt_connected")
    assert state is None

    entry = entity_registry.async_get(
        "binary_sensor.openevse_mock_config_mqtt_connected"
    )
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_missing_sensor_graceful_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test that missing binary sensor attributes are handled gracefully."""
    mock_charger.shaper_active = None

    with patch("homeassistant.components.openevse.PLATFORMS", [Platform.BINARY_SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # The binary sensor with missing attribute should be unknown
    state = hass.states.get("binary_sensor.openevse_mock_config_shaper_active")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Other binary sensors should still work
    state = hass.states.get("binary_sensor.openevse_mock_config_vehicle_connected")
    assert state is not None
    assert state.state == "on"


async def test_binary_sensor_unavailable_on_coordinator_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test binary sensors become unavailable when coordinator times out."""
    with patch("homeassistant.components.openevse.PLATFORMS", [Platform.BINARY_SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.openevse_mock_config_vehicle_connected")
    assert state
    assert state.state != STATE_UNAVAILABLE

    mock_charger.update.side_effect = TimeoutError("Connection timed out")
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.openevse_mock_config_vehicle_connected")
    assert state
    assert state.state == STATE_UNAVAILABLE
