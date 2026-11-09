"""Tests for the LaMetric integration."""

from unittest.mock import MagicMock

from demetriek import (
    LaMetricAuthenticationError,
    LaMetricConnectionError,
    LaMetricConnectionTimeoutError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lametric.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


@pytest.mark.parametrize(
    ("device_fixture", "serial_number"),
    [
        ("device", "SA110405124500W00BS9"),
        ("device_sa5", "SA52100000123TBNC"),
        ("device_sa5_bluetooth_unavailable", "SA52100000000TBNC"),
        ("device_wifi_connecting", "SA000000000000W00BS9"),
    ],
)
async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
    serial_number: str,
) -> None:
    """Test the device registry entry."""
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, serial_number), init_integration.entry_id
    )
    assert device_entry is not None
    assert device_entry == snapshot


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lametric: MagicMock,
) -> None:
    """Test the LaMetric configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_lametric.device.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_apps_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lametric: MagicMock,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test that setup succeeds when the device does not report its apps."""
    mock_lametric.apps.side_effect = LaMetricConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # The device entities keep working.
    state = hass.states.get("sensor.frenck_s_lametric_wi_fi_signal")
    assert state
    assert state.state == "21"

    # The app entities are unavailable until the apps can be fetched.
    for entity_id in (
        "sensor.frenck_s_lametric_current_app",
        "select.frenck_s_lametric_app",
    ):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "side_effect", [LaMetricConnectionTimeoutError, LaMetricConnectionError]
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lametric: MagicMock,
    side_effect: Exception,
) -> None:
    """Test the LaMetric configuration entry not ready."""
    mock_lametric.device.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_lametric.device.mock_calls) == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_authentication_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lametric: MagicMock,
    mock_lametric_local_auth: MagicMock,
) -> None:
    """Test trigger reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    mock_lametric.device.side_effect = LaMetricAuthenticationError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    # The device supports the button press, so the flow starts right there.
    assert flow["step_id"] == "press_button"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id
