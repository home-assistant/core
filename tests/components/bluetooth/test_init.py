"""Tests for the Bluetooth integration."""
from unittest.mock import AsyncMock, MagicMock, patch

import bleak
from bleak import BleakError
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

    with patch("homeassistant.components.bluetooth.HaBleakScanner.stop"), patch(
        "homeassistant.components.bluetooth.HaBleakScanner.start",
    ) as mock_bleak_scanner_start:
        yield mock_bleak_scanner_start

    # We need to drop the stop method from the object since we patched
    # out start and this fixture will expire before the stop method is called
    # when EVENT_HOMEASSISTANT_STOP is fired.
    if models.HA_BLEAK_SCANNER:
        models.HA_BLEAK_SCANNER.stop = AsyncMock()
    bleak.BleakScanner = scanner


async def test_setup_and_stop(hass, mock_bleak_scanner_start):
    """Test we and setup and stop the scanner."""
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


async def test_setup_and_stop_no_bluetooth(hass, caplog):
    """Test we fail gracefully when bluetooth is not available."""
    mock_bt = [
        {"domain": "switchbot", "service_uuid": "cba20d00-224d-11e6-9fb8-0002a5d5c51b"}
    ]
    with patch(
        "homeassistant.components.bluetooth.HaBleakScanner", side_effect=BleakError
    ) as mock_ha_bleak_scanner, patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert len(mock_ha_bleak_scanner.mock_calls) == 1
    assert "Could not create bluetooth scanner" in caplog.text


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
        if len(callbacks) >= 3:
            raise ValueError

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

        empty_device = BLEDevice("11:22:33:44:55:66", "empty")
        empty_adv = AdvertisementData(local_name="empty")

        # 3rd callback raises ValueError but is still tracked
        models.HA_BLEAK_SCANNER._callback(empty_device, empty_adv)
        await hass.async_block_till_done()

        cancel()

        # 4th callback should not be tracked since we canceled
        models.HA_BLEAK_SCANNER._callback(empty_device, empty_adv)
        await hass.async_block_till_done()

    assert len(callbacks) == 3

    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "wohand"
    assert service_info.manufacturer == "Nordic Semiconductor ASA"
    assert service_info.manufacturer_id == 89

    service_info: BluetoothServiceInfo = callbacks[1][0]
    assert service_info.name == "empty"
    assert service_info.manufacturer is None
    assert service_info.manufacturer_id is None

    service_info: BluetoothServiceInfo = callbacks[2][0]
    assert service_info.name == "empty"
    assert service_info.manufacturer is None
    assert service_info.manufacturer_id is None


async def test_wrapped_instance_with_filter(hass, mock_bleak_scanner_start):
    """Test consumers can use the wrapped instance with a filter as if it was normal BleakScanner."""
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=[]
    ), patch.object(hass.config_entries.flow, "async_init"):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    detected = []

    def _device_detected(
        device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Handle a detected device."""
        detected.append((device, advertisement_data))

    switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
    switchbot_adv = AdvertisementData(
        local_name="wohand",
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
    )
    empty_device = BLEDevice("11:22:33:44:55:66", "empty")
    empty_adv = AdvertisementData(local_name="empty")

    assert models.HA_BLEAK_SCANNER is not None
    scanner = models.HaBleakScannerWrapper(
        filters={"UUIDs": ["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]}
    )
    scanner.register_detection_callback(_device_detected)

    mock_discovered = [MagicMock()]
    type(models.HA_BLEAK_SCANNER).discovered_devices = mock_discovered
    models.HA_BLEAK_SCANNER._callback(switchbot_device, switchbot_adv)
    await hass.async_block_till_done()

    discovered = await scanner.discover(timeout=0)
    assert len(discovered) == 1
    assert discovered == mock_discovered
    assert len(detected) == 1

    scanner.register_detection_callback(_device_detected)
    # We should get a reply from the history when we register again
    assert len(detected) == 2
    scanner.register_detection_callback(_device_detected)
    # We should get a reply from the history when we register again
    assert len(detected) == 3

    type(models.HA_BLEAK_SCANNER).discovered_devices = []
    discovered = await scanner.discover(timeout=0)
    assert len(discovered) == 0
    assert discovered == []

    models.HA_BLEAK_SCANNER._callback(switchbot_device, switchbot_adv)
    assert len(detected) == 4

    # The filter we created in the wrapped scanner with should be respected
    # and we should not get another callback
    models.HA_BLEAK_SCANNER._callback(empty_device, empty_adv)
    assert len(detected) == 4


async def test_wrapped_instance_with_service_uuids(hass, mock_bleak_scanner_start):
    """Test consumers can use the wrapped instance with a service_uuids list as if it was normal BleakScanner."""
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=[]
    ), patch.object(hass.config_entries.flow, "async_init"):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    detected = []

    def _device_detected(
        device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Handle a detected device."""
        detected.append((device, advertisement_data))

    switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
    switchbot_adv = AdvertisementData(
        local_name="wohand",
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
    )
    empty_device = BLEDevice("11:22:33:44:55:66", "empty")
    empty_adv = AdvertisementData(local_name="empty")

    assert models.HA_BLEAK_SCANNER is not None
    scanner = models.HaBleakScannerWrapper(
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
    )
    scanner.register_detection_callback(_device_detected)

    type(models.HA_BLEAK_SCANNER).discovered_devices = [MagicMock()]
    for _ in range(2):
        models.HA_BLEAK_SCANNER._callback(switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

    assert len(detected) == 2

    # The UUIDs list we created in the wrapped scanner with should be respected
    # and we should not get another callback
    models.HA_BLEAK_SCANNER._callback(empty_device, empty_adv)
    assert len(detected) == 2


async def test_wrapped_instance_with_broken_callbacks(hass, mock_bleak_scanner_start):
    """Test broken callbacks do not cause the scanner to fail."""
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=[]
    ), patch.object(hass.config_entries.flow, "async_init"):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    detected = []

    def _device_detected(
        device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Handle a detected device."""
        if detected:
            raise ValueError
        detected.append((device, advertisement_data))

    switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
    switchbot_adv = AdvertisementData(
        local_name="wohand",
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
    )

    assert models.HA_BLEAK_SCANNER is not None
    scanner = models.HaBleakScannerWrapper(
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
    )
    scanner.register_detection_callback(_device_detected)

    models.HA_BLEAK_SCANNER._callback(switchbot_device, switchbot_adv)
    await hass.async_block_till_done()
    models.HA_BLEAK_SCANNER._callback(switchbot_device, switchbot_adv)
    await hass.async_block_till_done()
    assert len(detected) == 1
