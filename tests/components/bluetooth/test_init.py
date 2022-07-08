"""Tests for the Bluetooth integration."""
from unittest.mock import patch

from bleak.backends.scanner import AdvertisementData, BLEDevice
import pytest

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothServiceInfo,
    models,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.generated import bluetooth as bt_gen
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_bleak_scanner_start():
    """Fixture to mock starting the bleak scanner."""
    with patch(
        "homeassistant.components.bluetooth.HaBleakScanner.start",
    ) as mock_bleak_scanner_start:
        yield mock_bleak_scanner_start


async def test_setup_and_stop(hass, mock_bleak_scanner_start):
    """Test configured options for a device are loaded via config entry."""
    mock_bt = [
        {"domain": "switchbot", "service_uuid": "cba20d00-224d-11e6-9fb8-0002a5d5c51b"}
    ]
    with patch.object(bt_gen, "BLUETOOTH", mock_bt), patch.object(
        hass.config_entries.flow, "async_init"
    ):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert len(mock_bleak_scanner_start.mock_calls) == 1


async def test_discovery(hass, mock_bleak_scanner_start):
    """Test configured options for a device are loaded via config entry."""
    mock_bt = [
        {"domain": "switchbot", "service_uuid": "cba20d00-224d-11e6-9fb8-0002a5d5c51b"}
    ]
    with patch.object(bt_gen, "BLUETOOTH", mock_bt), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow:
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
        switchbot_adv = AdvertisementData(
            local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )

        models.HA_BLEAK_SCANNER._callback(switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "switchbot"


async def test_register_callbacks(hass, mock_bleak_scanner_start):
    """Test configured options for a device are loaded via config entry."""
    mock_bt = []
    callbacks = []

    def _fake_subscriber(
        service_info: BluetoothServiceInfo, change: BluetoothChange
    ) -> None:
        """Fake subscriber for the BleakScanner."""
        callbacks.append((service_info, change))

    with patch.object(bt_gen, "BLUETOOTH", mock_bt), patch.object(
        hass.config_entries.flow, "async_init"
    ):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        bluetooth.async_register_callback(
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
        await hass.async_block_till_done()

    assert len(callbacks) == 1

    service_info: BluetoothServiceInfo = callbacks[0][0]

    assert service_info.name == "wohand"
    assert service_info.manufacturer == "Nordic Semiconductor ASA"
    assert service_info.manufacturer_id == 89
