"""Tests for the Bluetooth integration."""
from unittest.mock import patch

import bleak
from bleak.backends.scanner import AdvertisementData, BLEDevice
import pytest

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothServiceInfo,
    models,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.setup import async_setup_component


@pytest.fixture()
def mock_bleak_scanner_start():
    """Fixture to mock starting the bleak scanner."""
    scanner = bleak.BleakScanner
    models.HA_BLEAK_SCANNER = None
    models.HaBleakScanner._history.clear()

    with patch(
        "homeassistant.components.bluetooth.HaBleakScanner.start",
    ) as mock_bleak_scanner_start:
        yield mock_bleak_scanner_start

    bleak.BleakScanner = scanner
    models.HaBleakScanner._history.clear()


async def test_setup_and_stop(hass, mock_bleak_scanner_start):
    """Test configured options for a device are loaded via config entry."""
    mock_bt = [
        {"domain": "switchbot", "service_uuid": "cba20d00-224d-11e6-9fb8-0002a5d5c51b"}
    ]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch.object(hass.config_entries.flow, "async_init"):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert len(mock_bleak_scanner_start.mock_calls) == 1


async def test_discovery_match_by_service_uuid(hass, mock_bleak_scanner_start):
    """Test bluetooth discovery match by service_uuid."""
    mock_bt = [
        {"domain": "switchbot", "service_uuid": "cba20d00-224d-11e6-9fb8-0002a5d5c51b"}
    ]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        wrong_device = BLEDevice("44:44:33:11:23:45", "wrong_name")
        wrong_adv = AdvertisementData(local_name="wrong_name", service_uuids=[])

        models.HA_BLEAK_SCANNER._callback(wrong_device, wrong_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0

        switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
        switchbot_adv = AdvertisementData(
            local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )

        models.HA_BLEAK_SCANNER._callback(switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "switchbot"


async def test_discovery_match_by_local_name(hass, mock_bleak_scanner_start):
    """Test bluetooth discovery match by local_name."""
    mock_bt = [{"domain": "switchbot", "local_name": "wohand"}]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        wrong_device = BLEDevice("44:44:33:11:23:45", "wrong_name")
        wrong_adv = AdvertisementData(local_name="wrong_name", service_uuids=[])

        models.HA_BLEAK_SCANNER._callback(wrong_device, wrong_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0

        switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
        switchbot_adv = AdvertisementData(local_name="wohand", service_uuids=[])

        models.HA_BLEAK_SCANNER._callback(switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "switchbot"


async def test_discovery_match_by_manufacturer_id_and_first_byte(
    hass, mock_bleak_scanner_start
):
    """Test bluetooth discovery match by manufacturer_id and manufacturer_data_first_byte."""
    mock_bt = [
        {
            "domain": "homekit_controller",
            "manufacturer_id": 76,
            "manufacturer_data_first_byte": 0x06,
        }
    ]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        hkc_device = BLEDevice("44:44:33:11:23:45", "lock")
        hkc_adv = AdvertisementData(
            local_name="lock", service_uuids=[], manufacturer_data={76: b"\x06"}
        )

        models.HA_BLEAK_SCANNER._callback(hkc_device, hkc_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "homekit_controller"
        mock_config_flow.reset_mock()

        # 2nd discovery should not generate another flow
        models.HA_BLEAK_SCANNER._callback(hkc_device, hkc_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0

        mock_config_flow.reset_mock()
        not_hkc_device = BLEDevice("44:44:33:11:23:21", "lock")
        not_hkc_adv = AdvertisementData(
            local_name="lock", service_uuids=[], manufacturer_data={76: b"\x02"}
        )

        models.HA_BLEAK_SCANNER._callback(not_hkc_device, not_hkc_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0
        not_apple_device = BLEDevice("44:44:33:11:23:23", "lock")
        not_apple_adv = AdvertisementData(
            local_name="lock", service_uuids=[], manufacturer_data={21: b"\x02"}
        )

        models.HA_BLEAK_SCANNER._callback(not_apple_device, not_apple_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0


async def test_register_callbacks(hass, mock_bleak_scanner_start):
    """Test configured options for a device are loaded via config entry."""
    mock_bt = []
    callbacks = []

    def _fake_subscriber(
        service_info: BluetoothServiceInfo, change: BluetoothChange
    ) -> None:
        """Fake subscriber for the BleakScanner."""
        callbacks.append((service_info, change))

    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch.object(hass.config_entries.flow, "async_init"):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {"service_uuids": {"cba20d00-224d-11e6-9fb8-0002a5d5c51b"}},
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
        switchbot_adv = AdvertisementData(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )

        models.HA_BLEAK_SCANNER._callback(switchbot_device, switchbot_adv)

        empty_device = BLEDevice("11:22:33:44:55:66", "empty")
        empty_adv = AdvertisementData(local_name="empty")

        models.HA_BLEAK_SCANNER._callback(empty_device, empty_adv)
        await hass.async_block_till_done()

        cancel()
        empty_device = BLEDevice("11:22:33:44:55:66", "empty")
        empty_adv = AdvertisementData(local_name="empty")

        models.HA_BLEAK_SCANNER._callback(empty_device, empty_adv)
        await hass.async_block_till_done()

    assert len(callbacks) == 2

    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "wohand"
    assert service_info.manufacturer == "Nordic Semiconductor ASA"
    assert service_info.manufacturer_id == 89

    service_info: BluetoothServiceInfo = callbacks[1][0]
    assert service_info.name == "empty"
    assert service_info.manufacturer is None
    assert service_info.manufacturer_id is None
