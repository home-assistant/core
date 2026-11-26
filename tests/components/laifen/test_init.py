"""Test the Laifen integration setup."""

from datetime import timedelta
import logging
from unittest.mock import MagicMock

from laifen_ble import LaifenConnectionError, UnsupportedStateError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_time_and_source_connectable,
    inject_bluetooth_service_info,
)

from homeassistant.components.bluetooth import MONOTONIC_TIME
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_UNAVAILABLE
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
from homeassistant.util import dt as dt_util

from . import ADDRESS, LAIFEN_SERVICE_INFO, NAME, setup_integration, wake_up
from .conftest import FIRMWARE_VERSION


def inject_old_advertisement(hass: HomeAssistant) -> None:
    """Inject the advertisement of the toothbrush as seen a minute ago."""
    inject_advertisement_with_time_and_source_connectable(
        hass,
        generate_ble_device(address=ADDRESS, name=NAME, details={}),
        generate_advertisement_data(
            local_name=NAME,
            manufacturer_data=LAIFEN_SERVICE_INFO.manufacturer_data,
        ),
        MONOTONIC_TIME() - 60,
        "local",
        connectable=True,
    )


async def test_setup_toothbrush_asleep(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush_class: MagicMock,
    mock_toothbrush: MagicMock,
) -> None:
    """Test that setup succeeds while the toothbrush is asleep."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_toothbrush_class.assert_called_once_with(ADDRESS)
    mock_toothbrush.connect.assert_not_awaited()


async def test_setup_does_not_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
) -> None:
    """Test that setup does not wait for an advertisement seen before it."""
    inject_bluetooth_service_info(hass, LAIFEN_SERVICE_INFO)

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_toothbrush.connect.assert_not_awaited()

    await wake_up(hass)

    mock_toothbrush.connect.assert_awaited_once()


async def test_connect_when_toothbrush_wakes_up(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test connecting when the toothbrush starts advertising."""
    await setup_integration(hass, mock_config_entry)

    await wake_up(hass)

    mock_toothbrush.set_ble_device.assert_called_once()
    mock_toothbrush.connect.assert_awaited_once()
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_BLUETOOTH, ADDRESS), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == FIRMWARE_VERSION
    assert device.model == "Wave"
    assert device.model_id == "LFTB01-P"


async def test_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
) -> None:
    """Test that the next advertisement is tried after a failed connection."""
    await setup_integration(hass, mock_config_entry)
    mock_toothbrush.connect.side_effect = LaifenConnectionError

    await wake_up(hass)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_toothbrush.connect.assert_awaited_once()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await wake_up(hass)

    assert mock_toothbrush.connect.await_count == 2


async def test_unsupported_firmware(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a toothbrush with an unsupported state is not retried."""
    await setup_integration(hass, mock_config_entry)
    mock_toothbrush.connect.side_effect = UnsupportedStateError("length 15")

    await wake_up(hass)

    assert (
        "homeassistant.components.laifen.coordinator",
        logging.WARNING,
        f"{NAME} sends a state that is not supported: length 15",
    ) in caplog.record_tuples

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await wake_up(hass)

    mock_toothbrush.connect.assert_awaited_once()


async def test_old_advertisement_is_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
) -> None:
    """Test that an old advertisement does not hide the next wake-up."""
    await setup_integration(hass, mock_config_entry)

    inject_old_advertisement(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_toothbrush.connect.assert_not_awaited()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await wake_up(hass)

    mock_toothbrush.connect.assert_awaited_once()


async def test_advertisement_while_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
) -> None:
    """Test that advertisements do not reconnect a connected toothbrush."""
    await setup_integration(hass, mock_config_entry)
    await wake_up(hass)

    inject_bluetooth_service_info(
        hass,
        BluetoothServiceInfo(
            name=NAME,
            address=ADDRESS,
            rssi=-50,
            manufacturer_data={0xAA00: bytes.fromhex("3412000000c1")},
            service_data={},
            service_uuids=[],
            source="local",
        ),
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_toothbrush.connect.assert_awaited_once()
    mock_toothbrush.update.assert_not_awaited()


async def test_reconnect_after_sleep(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the unchanged advertisement of a waking toothbrush reconnects."""
    caplog.set_level(logging.INFO)
    await setup_integration(hass, mock_config_entry)
    await wake_up(hass)
    mock_toothbrush.notify()
    await hass.async_block_till_done()
    assert caplog.text.count(f"Connected to {NAME}") == 1

    await mock_toothbrush.disconnect()
    await hass.async_block_till_done()
    assert f"{NAME} is asleep or out of range" in caplog.text

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await wake_up(hass)

    assert mock_toothbrush.connect.await_count == 2


async def test_reconnect_after_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
) -> None:
    """Test that the toothbrush is connected again after a reload."""
    await setup_integration(hass, mock_config_entry)
    await wake_up(hass)
    inject_old_advertisement(hass)

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_toothbrush.disconnect.assert_awaited_once()
    mock_toothbrush.connect.assert_awaited_once()

    await wake_up(hass)

    assert mock_toothbrush.connect.await_count == 2


async def test_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
) -> None:
    """Test unloading disconnects from the toothbrush."""
    await setup_integration(hass, mock_config_entry)
    await wake_up(hass)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_toothbrush.disconnect.assert_awaited_once()


async def test_disconnect_when_home_assistant_stops(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the connection is closed when Home Assistant stops."""
    caplog.set_level(logging.INFO)
    await setup_integration(hass, mock_config_entry)
    await wake_up(hass)

    hass.set_state(CoreState.stopping)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_toothbrush.disconnect.assert_awaited_once()
    assert f"{NAME} is asleep or out of range" not in caplog.text

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await wake_up(hass)

    mock_toothbrush.connect.assert_awaited_once()


async def test_no_connect_after_home_assistant_stops(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
) -> None:
    """Test that a connect waiting in the debouncer does not run after stop."""
    await setup_integration(hass, mock_config_entry)
    connect = mock_toothbrush.connect.side_effect
    mock_toothbrush.connect.side_effect = LaifenConnectionError
    await wake_up(hass)
    mock_toothbrush.connect.side_effect = connect
    await wake_up(hass)

    hass.set_state(CoreState.stopping)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_toothbrush.connect.assert_awaited_once()
    assert not mock_toothbrush.connected


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.lftb01_p_1234_battery",
        "sensor.lftb01_p_1234_last_brushing_duration",
    ],
)
async def test_entities_unavailable_when_update_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
    entity_id: str,
) -> None:
    """Test that the entities follow the availability of the coordinator."""
    await setup_integration(hass, mock_config_entry)
    await wake_up(hass)
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE
    mock_toothbrush.update.side_effect = RuntimeError

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_update_while_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
) -> None:
    """Test that the state is read every minute while connected."""
    await setup_integration(hass, mock_config_entry)
    await wake_up(hass)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()

    mock_toothbrush.update.assert_awaited_once()

    mock_toothbrush.disconnect.assert_not_awaited()

    mock_toothbrush.update.side_effect = LaifenConnectionError
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=122))
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_toothbrush.update.await_count == 2
    mock_toothbrush.disconnect.assert_awaited_once()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=133))
    await wake_up(hass)

    assert mock_toothbrush.connect.await_count == 2


async def test_firmware_version_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that the firmware version is stored on the device once known."""
    await setup_integration(hass, mock_config_entry)
    mock_toothbrush.notify()
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_BLUETOOTH, ADDRESS), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Laifen"
    assert device.sw_version is None

    mock_toothbrush.firmware_version = "V2.0.93.XXX.T01.B00.Y44.303"
    mock_toothbrush.notify()
    await hass.async_block_till_done()

    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.sw_version == "V2.0.93.XXX.T01.B00.Y44.303"
