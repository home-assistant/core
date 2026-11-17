"""Tests for the System Bridge binary sensor platform."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.models.fixtures.modules.system import FIXTURE_SYSTEM
from systembridgeconnector.models.modules import Module

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.fixture(autouse=True)
def binary_sensor_only() -> Generator[None]:
    """Enable only the binary sensor platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        yield


@pytest.mark.usefixtures(
    "mock_version", "mock_websocket_client", "entity_registry_enabled_by_default"
)
async def test_binary_sensor_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the binary sensor platform."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_version")
async def test_binary_sensor_platform_no_battery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test setup of the binary sensor platform without battery data."""
    mock_websocket_client.get_data.return_value = replace(
        mock_websocket_client.get_data.return_value, battery=None
    )
    mock_websocket_client.listen.side_effect = None
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("binary_sensor.hostname_session_lock")
    assert not hass.states.get("binary_sensor.hostname_ac_power")
    assert not hass.states.get("binary_sensor.hostname_charging")


@pytest.mark.parametrize(
    "entity_id",
    ["binary_sensor.hostname_ac_power", "binary_sensor.hostname_charging"],
)
@pytest.mark.usefixtures("init_integration")
async def test_binary_sensor_battery_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test battery binary sensors are unknown when the battery data goes missing."""
    await mock_config_entry.runtime_data.async_handle_module(Module.BATTERY, None)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("locked", "expected_state"),
    [
        pytest.param(True, STATE_OFF, id="locked"),
        pytest.param(False, STATE_ON, id="unlocked"),
        pytest.param(None, STATE_UNKNOWN, id="unknown"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_session_lock(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    locked: bool | None,
    expected_state: str,
) -> None:
    """Test the session lock is on when unlocked, as the lock device class expects."""
    callback = mock_websocket_client.listen.call_args.kwargs["callback"]

    await callback(Module.SYSTEM, replace(FIXTURE_SYSTEM, locked=locked))
    await hass.async_block_till_done()

    assert (state := hass.states.get("binary_sensor.hostname_session_lock"))
    assert state.state == expected_state
