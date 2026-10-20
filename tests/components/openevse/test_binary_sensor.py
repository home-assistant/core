"""Tests for the OpenEVSE binary sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


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
    freezer: FrozenDateTimeFactory,
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
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.openevse_mock_config_vehicle_connected")
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("raw_status", "expected_state"),
    [
        pytest.param("active", "on", id="active"),
        pytest.param("disabled", "off", id="disabled"),
        pytest.param(None, STATE_UNKNOWN, id="none"),
    ],
)
async def test_station_status_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
    raw_status: str | None,
    expected_state: str,
) -> None:
    """Test station status binary sensor states."""
    mock_charger.status = raw_status

    with patch("homeassistant.components.openevse.PLATFORMS", [Platform.BINARY_SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    state = hass.states.get("binary_sensor.openevse_mock_config_station_status")
    assert state is not None
    assert state.state == expected_state
