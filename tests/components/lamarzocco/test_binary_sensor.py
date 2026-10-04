"""Tests for La Marzocco binary sensors."""

from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock, patch

from freezegun.api import FrozenDateTimeFactory
from pylamarzocco.exceptions import RequestNotSuccessful
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = pytest.mark.usefixtures("mock_websocket_terminated")


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_ble_device_from_address"
)
async def test_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry_bluetooth: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco binary sensors."""

    with patch(
        "homeassistant.components.lamarzocco.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await async_init_integration(hass, mock_config_entry_bluetooth)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_bluetooth.entry_id
    )


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_ble_device_from_address"
)
async def test_bluetooth_connected(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
) -> None:
    """Test the Bluetooth connected binary sensor follows the connection."""
    await async_init_integration(hass, mock_config_entry_bluetooth)

    entity_id = "binary_sensor.gs012345_bluetooth_connected"
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    # the library reports connection changes through the registered callback
    mock_lamarzocco.bluetooth_connected = False
    connection_callback = (
        mock_lamarzocco.register_bluetooth_connection_callback.call_args.args[0]
    )
    connection_callback(False)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    unregister = mock_lamarzocco.register_bluetooth_connection_callback.return_value
    await hass.config_entries.async_unload(mock_config_entry_bluetooth.entry_id)
    unregister.assert_called_once()


async def test_brew_active_unavailable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_websocket_terminated: PropertyMock,
) -> None:
    """Test the La Marzocco brew active becomes unavailable."""

    mock_websocket_terminated.return_value = True
    await async_init_integration(hass, mock_config_entry)
    state = hass.states.get(
        f"binary_sensor.{mock_lamarzocco.serial_number}_brewing_active"
    )
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_going_unavailable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor is going unavailable after an unsuccessful update."""
    brewing_active_sensor = (
        f"binary_sensor.{mock_lamarzocco.serial_number}_brewing_active"
    )
    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get(brewing_active_sensor)
    assert state
    assert state.state != STATE_UNAVAILABLE

    mock_lamarzocco.websocket.connected = False
    mock_lamarzocco.ensure_token_valid.side_effect = RequestNotSuccessful("")
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(brewing_active_sensor)
    assert state
    assert state.state == STATE_UNAVAILABLE
