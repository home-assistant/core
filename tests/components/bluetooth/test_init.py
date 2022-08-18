"""Tests for the Bluetooth integration."""
import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch

from bleak import BleakError
from bleak.backends.scanner import AdvertisementData, BLEDevice
import pytest

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfo,
    async_process_advertisements,
    async_rediscover_address,
    async_track_unavailable,
    models,
    scanner,
)
from homeassistant.components.bluetooth.const import (
    DEFAULT_ADDRESS,
    SOURCE_LOCAL,
    UNAVAILABLE_TRACK_SECONDS,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    _get_manager,
    async_setup_with_default_adapter,
    inject_advertisement,
    patch_discovered_devices,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_and_stop(hass, mock_bleak_scanner_start, enable_bluetooth):
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


async def test_setup_and_stop_no_bluetooth(hass, caplog, macos_adapter):
    """Test we fail gracefully when bluetooth is not available."""
    mock_bt = [
        {"domain": "switchbot", "service_uuid": "cba20d00-224d-11e6-9fb8-0002a5d5c51b"}
    ]
    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner",
        side_effect=BleakError,
    ) as mock_ha_bleak_scanner, patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        await async_setup_with_default_adapter(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert len(mock_ha_bleak_scanner.mock_calls) == 1
    assert "Failed to initialize Bluetooth" in caplog.text


async def test_setup_and_stop_broken_bluetooth(hass, caplog, macos_adapter):
    """Test we fail gracefully when bluetooth/dbus is broken."""
    mock_bt = []
    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=BleakError,
    ), patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        await async_setup_with_default_adapter(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "Failed to start Bluetooth" in caplog.text
    assert len(bluetooth.async_discovered_service_info(hass)) == 0


async def test_setup_and_stop_broken_bluetooth_hanging(hass, caplog, macos_adapter):
    """Test we fail gracefully when bluetooth/dbus is hanging."""
    mock_bt = []

    async def _mock_hang():
        await asyncio.sleep(1)

    with patch.object(scanner, "START_TIMEOUT", 0), patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=_mock_hang,
    ), patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        await async_setup_with_default_adapter(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "Timed out starting Bluetooth" in caplog.text


async def test_setup_and_retry_adapter_not_yet_available(hass, caplog, macos_adapter):
    """Test we retry if the adapter is not yet available."""
    mock_bt = []
    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=BleakError,
    ), patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        await async_setup_with_default_adapter(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(bluetooth.DOMAIN)[0]

    assert "Failed to start Bluetooth" in caplog.text
    assert len(bluetooth.async_discovered_service_info(hass)) == 0
    assert entry.state == ConfigEntryState.SETUP_RETRY

    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
        await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.stop",
    ):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()


async def test_no_race_during_manual_reload_in_retry_state(hass, caplog, macos_adapter):
    """Test we can successfully reload when the entry is in a retry state."""
    mock_bt = []
    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=BleakError,
    ), patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        await async_setup_with_default_adapter(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(bluetooth.DOMAIN)[0]

    assert "Failed to start Bluetooth" in caplog.text
    assert len(bluetooth.async_discovered_service_info(hass)) == 0
    assert entry.state == ConfigEntryState.SETUP_RETRY

    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.stop",
    ):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()


async def test_calling_async_discovered_devices_no_bluetooth(
    hass, caplog, macos_adapter
):
    """Test we fail gracefully when asking for discovered devices and there is no blueooth."""
    mock_bt = []
    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner",
        side_effect=FileNotFoundError,
    ), patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        await async_setup_with_default_adapter(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "Failed to initialize Bluetooth" in caplog.text
    assert not bluetooth.async_discovered_service_info(hass)
    assert not bluetooth.async_address_present(hass, "aa:bb:bb:dd:ee:ff")


async def test_discovery_match_by_service_uuid(
    hass, mock_bleak_scanner_start, enable_bluetooth
):
    """Test bluetooth discovery match by service_uuid."""
    mock_bt = [
        {"domain": "switchbot", "service_uuid": "cba20d00-224d-11e6-9fb8-0002a5d5c51b"}
    ]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        await async_setup_with_default_adapter(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        wrong_device = BLEDevice("44:44:33:11:23:45", "wrong_name")
        wrong_adv = AdvertisementData(local_name="wrong_name", service_uuids=[])

        inject_advertisement(wrong_device, wrong_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0

        switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
        switchbot_adv = AdvertisementData(
            local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )

        inject_advertisement(switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "switchbot"


async def test_discovery_match_by_local_name(
    hass, mock_bleak_scanner_start, macos_adapter
):
    """Test bluetooth discovery match by local_name."""
    mock_bt = [{"domain": "switchbot", "local_name": "wohand"}]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        wrong_device = BLEDevice("44:44:33:11:23:45", "wrong_name")
        wrong_adv = AdvertisementData(local_name="wrong_name", service_uuids=[])

        inject_advertisement(wrong_device, wrong_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0

        switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
        switchbot_adv = AdvertisementData(local_name="wohand", service_uuids=[])

        inject_advertisement(switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "switchbot"


async def test_discovery_match_by_manufacturer_id_and_manufacturer_data_start(
    hass, mock_bleak_scanner_start, macos_adapter
):
    """Test bluetooth discovery match by manufacturer_id and manufacturer_data_start."""
    mock_bt = [
        {
            "domain": "homekit_controller",
            "manufacturer_id": 76,
            "manufacturer_data_start": [0x06, 0x02, 0x03],
        }
    ]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        hkc_device = BLEDevice("44:44:33:11:23:45", "lock")
        hkc_adv_no_mfr_data = AdvertisementData(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={},
        )
        hkc_adv = AdvertisementData(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={76: b"\x06\x02\x03\x99"},
        )

        # 1st discovery with no manufacturer data
        # should not trigger config flow
        inject_advertisement(hkc_device, hkc_adv_no_mfr_data)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()

        # 2nd discovery with manufacturer data
        # should trigger a config flow
        inject_advertisement(hkc_device, hkc_adv)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "homekit_controller"
        mock_config_flow.reset_mock()

        # 3rd discovery should not generate another flow
        inject_advertisement(hkc_device, hkc_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0

        mock_config_flow.reset_mock()
        not_hkc_device = BLEDevice("44:44:33:11:23:21", "lock")
        not_hkc_adv = AdvertisementData(
            local_name="lock", service_uuids=[], manufacturer_data={76: b"\x02"}
        )

        inject_advertisement(not_hkc_device, not_hkc_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0
        not_apple_device = BLEDevice("44:44:33:11:23:23", "lock")
        not_apple_adv = AdvertisementData(
            local_name="lock", service_uuids=[], manufacturer_data={21: b"\x02"}
        )

        inject_advertisement(not_apple_device, not_apple_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0


async def test_discovery_match_by_service_data_uuid_then_others(
    hass, mock_bleak_scanner_start, macos_adapter
):
    """Test bluetooth discovery match by service_data_uuid and then other fields."""
    mock_bt = [
        {
            "domain": "my_domain",
            "service_data_uuid": "0000fd3d-0000-1000-8000-00805f9b34fb",
        },
        {
            "domain": "my_domain",
            "service_uuid": "0000fd3d-0000-1000-8000-00805f9b34fc",
        },
        {
            "domain": "other_domain",
            "manufacturer_id": 323,
        },
    ]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        device = BLEDevice("44:44:33:11:23:45", "lock")
        adv_without_service_data_uuid = AdvertisementData(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={},
        )
        adv_with_mfr_data = AdvertisementData(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={323: b"\x01\x02\x03"},
            service_data={},
        )
        adv_with_service_data_uuid = AdvertisementData(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={},
            service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"\x01\x02\x03"},
        )
        adv_with_service_data_uuid_and_mfr_data = AdvertisementData(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={323: b"\x01\x02\x03"},
            service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"\x01\x02\x03"},
        )
        adv_with_service_data_uuid_and_mfr_data_and_service_uuid = AdvertisementData(
            local_name="lock",
            manufacturer_data={323: b"\x01\x02\x03"},
            service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"\x01\x02\x03"},
            service_uuids=["0000fd3d-0000-1000-8000-00805f9b34fd"],
        )
        adv_with_service_uuid = AdvertisementData(
            local_name="lock",
            manufacturer_data={},
            service_data={},
            service_uuids=["0000fd3d-0000-1000-8000-00805f9b34fd"],
        )
        # 1st discovery should not generate a flow because the
        # service_data_uuid is not in the advertisement
        inject_advertisement(device, adv_without_service_data_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()

        # 2nd discovery should not generate a flow because the
        # service_data_uuid is not in the advertisement
        inject_advertisement(device, adv_without_service_data_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()

        # 3rd discovery should generate a flow because the
        # manufacturer_data is in the advertisement
        inject_advertisement(device, adv_with_mfr_data)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "other_domain"
        mock_config_flow.reset_mock()

        # 4th discovery should generate a flow because the
        # service_data_uuid is in the advertisement and
        # we never saw a service_data_uuid before
        inject_advertisement(device, adv_with_service_data_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "my_domain"
        mock_config_flow.reset_mock()

        # 5th discovery should not generate a flow because the
        # we already saw an advertisement with the service_data_uuid
        inject_advertisement(device, adv_with_service_data_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0

        # 6th discovery should not generate a flow because the
        # manufacturer_data is in the advertisement
        # and we saw manufacturer_data before
        inject_advertisement(device, adv_with_service_data_uuid_and_mfr_data)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()

        # 7th discovery should generate a flow because the
        # service_uuids is in the advertisement
        # and we never saw service_uuids before
        inject_advertisement(
            device, adv_with_service_data_uuid_and_mfr_data_and_service_uuid
        )
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 2
        assert {
            mock_config_flow.mock_calls[0][1][0],
            mock_config_flow.mock_calls[1][1][0],
        } == {"my_domain", "other_domain"}
        mock_config_flow.reset_mock()

        # 8th discovery should not generate a flow
        # since all fields have been seen at this point
        inject_advertisement(
            device, adv_with_service_data_uuid_and_mfr_data_and_service_uuid
        )
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()

        # 9th discovery should not generate a flow
        # since all fields have been seen at this point
        inject_advertisement(device, adv_with_service_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0

        # 10th discovery should not generate a flow
        # since all fields have been seen at this point
        inject_advertisement(device, adv_with_service_data_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0

        # 11th discovery should not generate a flow
        # since all fields have been seen at this point
        inject_advertisement(device, adv_without_service_data_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0


async def test_discovery_match_first_by_service_uuid_and_then_manufacturer_id(
    hass, mock_bleak_scanner_start, macos_adapter
):
    """Test bluetooth discovery matches twice for service_uuid and then manufacturer_id."""
    mock_bt = [
        {
            "domain": "my_domain",
            "manufacturer_id": 76,
        },
        {
            "domain": "my_domain",
            "service_uuid": "0000fd3d-0000-1000-8000-00805f9b34fc",
        },
    ]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        device = BLEDevice("44:44:33:11:23:45", "lock")
        adv_service_uuids = AdvertisementData(
            local_name="lock",
            service_uuids=["0000fd3d-0000-1000-8000-00805f9b34fc"],
            manufacturer_data={},
        )
        adv_manufacturer_data = AdvertisementData(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={76: b"\x06\x02\x03\x99"},
        )

        # 1st discovery with matches service_uuid
        # should trigger config flow
        inject_advertisement(device, adv_service_uuids)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "my_domain"
        mock_config_flow.reset_mock()

        # 2nd discovery with manufacturer data
        # should trigger a config flow
        inject_advertisement(device, adv_manufacturer_data)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "my_domain"
        mock_config_flow.reset_mock()

        # 3rd discovery should not generate another flow
        inject_advertisement(device, adv_service_uuids)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0

        # 4th discovery should not generate another flow
        inject_advertisement(device, adv_manufacturer_data)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0


async def test_rediscovery(hass, mock_bleak_scanner_start, enable_bluetooth):
    """Test bluetooth discovery can be re-enabled for a given domain."""
    mock_bt = [
        {"domain": "switchbot", "service_uuid": "cba20d00-224d-11e6-9fb8-0002a5d5c51b"}
    ]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        await async_setup_with_default_adapter(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
        switchbot_adv = AdvertisementData(
            local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )

        inject_advertisement(switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        inject_advertisement(switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "switchbot"

        async_rediscover_address(hass, "44:44:33:11:23:45")

        inject_advertisement(switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 2
        assert mock_config_flow.mock_calls[1][1][0] == "switchbot"


async def test_async_discovered_device_api(
    hass, mock_bleak_scanner_start, macos_adapter
):
    """Test the async_discovered_device API."""
    mock_bt = []
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch(
        "bleak.BleakScanner.discovered_devices",  # Must patch before we setup
        [MagicMock(address="44:44:33:11:23:45")],
    ):
        assert not bluetooth.async_discovered_service_info(hass)
        assert not bluetooth.async_address_present(hass, "44:44:22:22:11:22")
        await async_setup_with_default_adapter(hass)

        with patch.object(hass.config_entries.flow, "async_init"):
            hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
            await hass.async_block_till_done()

            assert len(mock_bleak_scanner_start.mock_calls) == 1

            assert not bluetooth.async_discovered_service_info(hass)

            wrong_device = BLEDevice("44:44:33:11:23:42", "wrong_name")
            wrong_adv = AdvertisementData(local_name="wrong_name", service_uuids=[])
            inject_advertisement(wrong_device, wrong_adv)
            switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
            switchbot_adv = AdvertisementData(local_name="wohand", service_uuids=[])
            inject_advertisement(switchbot_device, switchbot_adv)
            wrong_device_went_unavailable = False
            switchbot_device_went_unavailable = False

            @callback
            def _wrong_device_unavailable_callback(_address: str) -> None:
                """Wrong device unavailable callback."""
                nonlocal wrong_device_went_unavailable
                wrong_device_went_unavailable = True
                raise ValueError("blow up")

            @callback
            def _switchbot_device_unavailable_callback(_address: str) -> None:
                """Switchbot device unavailable callback."""
                nonlocal switchbot_device_went_unavailable
                switchbot_device_went_unavailable = True

            wrong_device_unavailable_cancel = async_track_unavailable(
                hass, _wrong_device_unavailable_callback, wrong_device.address
            )
            switchbot_device_unavailable_cancel = async_track_unavailable(
                hass, _switchbot_device_unavailable_callback, switchbot_device.address
            )

            async_fire_time_changed(
                hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
            )
            await hass.async_block_till_done()

            service_infos = bluetooth.async_discovered_service_info(hass)
            assert switchbot_device_went_unavailable is False
            assert wrong_device_went_unavailable is True

            # See the devices again
            inject_advertisement(wrong_device, wrong_adv)
            inject_advertisement(switchbot_device, switchbot_adv)
            # Cancel the callbacks
            wrong_device_unavailable_cancel()
            switchbot_device_unavailable_cancel()
            wrong_device_went_unavailable = False
            switchbot_device_went_unavailable = False

            # Verify the cancel is effective
            async_fire_time_changed(
                hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
            )
            await hass.async_block_till_done()
            assert switchbot_device_went_unavailable is False
            assert wrong_device_went_unavailable is False

            assert len(service_infos) == 1
            # wrong_name should not appear because bleak no longer sees it
            assert service_infos[0].name == "wohand"
            assert service_infos[0].source == SOURCE_LOCAL
            assert isinstance(service_infos[0].device, BLEDevice)
            assert isinstance(service_infos[0].advertisement, AdvertisementData)

            assert bluetooth.async_address_present(hass, "44:44:33:11:23:42") is False
            assert bluetooth.async_address_present(hass, "44:44:33:11:23:45") is True


async def test_register_callbacks(hass, mock_bleak_scanner_start, enable_bluetooth):
    """Test registering a callback."""
    mock_bt = []
    callbacks = []

    def _fake_subscriber(
        service_info: BluetoothServiceInfo,
        change: BluetoothChange,
    ) -> None:
        """Fake subscriber for the BleakScanner."""
        callbacks.append((service_info, change))
        if len(callbacks) >= 3:
            raise ValueError

    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch.object(hass.config_entries.flow, "async_init"):
        await async_setup_with_default_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {"service_uuids": {"cba20d00-224d-11e6-9fb8-0002a5d5c51b"}},
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
        switchbot_adv = AdvertisementData(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )

        inject_advertisement(switchbot_device, switchbot_adv)

        empty_device = BLEDevice("11:22:33:44:55:66", "empty")
        empty_adv = AdvertisementData(local_name="empty")

        inject_advertisement(empty_device, empty_adv)
        await hass.async_block_till_done()

        empty_device = BLEDevice("11:22:33:44:55:66", "empty")
        empty_adv = AdvertisementData(local_name="empty")

        # 3rd callback raises ValueError but is still tracked
        inject_advertisement(empty_device, empty_adv)
        await hass.async_block_till_done()

        cancel()

        # 4th callback should not be tracked since we canceled
        inject_advertisement(empty_device, empty_adv)
        await hass.async_block_till_done()

    assert len(callbacks) == 3

    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "wohand"
    assert service_info.source == SOURCE_LOCAL
    assert service_info.manufacturer == "Nordic Semiconductor ASA"
    assert service_info.manufacturer_id == 89

    service_info: BluetoothServiceInfo = callbacks[1][0]
    assert service_info.name == "empty"
    assert service_info.source == SOURCE_LOCAL
    assert service_info.manufacturer is None
    assert service_info.manufacturer_id is None

    service_info: BluetoothServiceInfo = callbacks[2][0]
    assert service_info.name == "empty"
    assert service_info.source == SOURCE_LOCAL
    assert service_info.manufacturer is None
    assert service_info.manufacturer_id is None


async def test_register_callback_by_address(
    hass, mock_bleak_scanner_start, enable_bluetooth
):
    """Test registering a callback by address."""
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
    ):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {"address": "44:44:33:11:23:45"},
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
        switchbot_adv = AdvertisementData(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )

        inject_advertisement(switchbot_device, switchbot_adv)

        empty_device = BLEDevice("11:22:33:44:55:66", "empty")
        empty_adv = AdvertisementData(local_name="empty")

        inject_advertisement(empty_device, empty_adv)
        await hass.async_block_till_done()

        empty_device = BLEDevice("11:22:33:44:55:66", "empty")
        empty_adv = AdvertisementData(local_name="empty")

        # 3rd callback raises ValueError but is still tracked
        inject_advertisement(empty_device, empty_adv)
        await hass.async_block_till_done()

        cancel()

        # 4th callback should not be tracked since we canceled
        inject_advertisement(empty_device, empty_adv)
        await hass.async_block_till_done()

        # Now register again with a callback that fails to
        # make sure we do not perm fail
        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {"address": "44:44:33:11:23:45"},
            BluetoothScanningMode.ACTIVE,
        )
        cancel()

        # Now register again, since the 3rd callback
        # should fail but we should still record it
        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {"address": "44:44:33:11:23:45"},
            BluetoothScanningMode.ACTIVE,
        )
        cancel()

    assert len(callbacks) == 3

    for idx in range(3):
        service_info: BluetoothServiceInfo = callbacks[idx][0]
        assert service_info.name == "wohand"
        assert service_info.manufacturer == "Nordic Semiconductor ASA"
        assert service_info.manufacturer_id == 89


async def test_register_callback_survives_reload(
    hass, mock_bleak_scanner_start, enable_bluetooth
):
    """Test registering a callback by address survives bluetooth being reloaded."""
    mock_bt = []
    callbacks = []

    def _fake_subscriber(
        service_info: BluetoothServiceInfo, change: BluetoothChange
    ) -> None:
        """Fake subscriber for the BleakScanner."""
        callbacks.append((service_info, change))

    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        await async_setup_with_default_adapter(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    bluetooth.async_register_callback(
        hass,
        _fake_subscriber,
        {"address": "44:44:33:11:23:45"},
        BluetoothScanningMode.ACTIVE,
    )

    assert len(mock_bleak_scanner_start.mock_calls) == 1

    switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
    switchbot_adv = AdvertisementData(
        local_name="wohand",
        service_uuids=["zba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
    )

    inject_advertisement(switchbot_device, switchbot_adv)
    assert len(callbacks) == 1
    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "wohand"
    assert service_info.manufacturer == "Nordic Semiconductor ASA"
    assert service_info.manufacturer_id == 89

    entry = hass.config_entries.async_entries(bluetooth.DOMAIN)[0]
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    inject_advertisement(switchbot_device, switchbot_adv)
    assert len(callbacks) == 2
    service_info: BluetoothServiceInfo = callbacks[1][0]
    assert service_info.name == "wohand"
    assert service_info.manufacturer == "Nordic Semiconductor ASA"
    assert service_info.manufacturer_id == 89


async def test_process_advertisements_bail_on_good_advertisement(
    hass: HomeAssistant, mock_bleak_scanner_start, enable_bluetooth
):
    """Test as soon as we see a 'good' advertisement we return it."""
    done = asyncio.Future()

    def _callback(service_info: BluetoothServiceInfo) -> bool:
        done.set_result(None)
        return len(service_info.service_data) > 0

    handle = hass.async_create_task(
        async_process_advertisements(
            hass,
            _callback,
            {"address": "aa:44:33:11:23:45"},
            BluetoothScanningMode.ACTIVE,
            5,
        )
    )

    while not done.done():
        device = BLEDevice("aa:44:33:11:23:45", "wohand")
        adv = AdvertisementData(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51a"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fa": b"H\x10c"},
        )

        inject_advertisement(device, adv)
        inject_advertisement(device, adv)
        inject_advertisement(device, adv)

        await asyncio.sleep(0)

    result = await handle
    assert result.name == "wohand"


async def test_process_advertisements_ignore_bad_advertisement(
    hass: HomeAssistant, mock_bleak_scanner_start, enable_bluetooth
):
    """Check that we ignore bad advertisements."""
    done = asyncio.Event()
    return_value = asyncio.Event()

    device = BLEDevice("aa:44:33:11:23:45", "wohand")
    adv = AdvertisementData(
        local_name="wohand",
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51a"],
        manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fa": b""},
    )

    def _callback(service_info: BluetoothServiceInfo) -> bool:
        done.set()
        return return_value.is_set()

    handle = hass.async_create_task(
        async_process_advertisements(
            hass,
            _callback,
            {"address": "aa:44:33:11:23:45"},
            BluetoothScanningMode.ACTIVE,
            5,
        )
    )

    # The goal of this loop is to make sure that async_process_advertisements sees at least one
    # callback that returns False
    while not done.is_set():
        inject_advertisement(device, adv)
        await asyncio.sleep(0)

    # Set the return value and mutate the advertisement
    # Check that scan ends and correct advertisement data is returned
    return_value.set()
    adv.service_data["00000d00-0000-1000-8000-00805f9b34fa"] = b"H\x10c"
    inject_advertisement(device, adv)
    await asyncio.sleep(0)

    result = await handle
    assert result.service_data["00000d00-0000-1000-8000-00805f9b34fa"] == b"H\x10c"


async def test_process_advertisements_timeout(
    hass, mock_bleak_scanner_start, enable_bluetooth
):
    """Test we timeout if no advertisements at all."""

    def _callback(service_info: BluetoothServiceInfo) -> bool:
        return False

    with pytest.raises(asyncio.TimeoutError):
        await async_process_advertisements(
            hass, _callback, {}, BluetoothScanningMode.ACTIVE, 0
        )


async def test_wrapped_instance_with_filter(
    hass, mock_bleak_scanner_start, enable_bluetooth
):
    """Test consumers can use the wrapped instance with a filter as if it was normal BleakScanner."""
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=[]
    ):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init"):
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

        assert _get_manager() is not None
        scanner = models.HaBleakScannerWrapper(
            filters={"UUIDs": ["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]}
        )
        scanner.register_detection_callback(_device_detected)

        inject_advertisement(switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        discovered = await scanner.discover(timeout=0)
        assert len(discovered) == 1
        assert discovered == [switchbot_device]
        assert len(detected) == 1

        scanner.register_detection_callback(_device_detected)
        # We should get a reply from the history when we register again
        assert len(detected) == 2
        scanner.register_detection_callback(_device_detected)
        # We should get a reply from the history when we register again
        assert len(detected) == 3

        with patch_discovered_devices([]):
            discovered = await scanner.discover(timeout=0)
            assert len(discovered) == 0
            assert discovered == []

        inject_advertisement(switchbot_device, switchbot_adv)
        assert len(detected) == 4

        # The filter we created in the wrapped scanner with should be respected
        # and we should not get another callback
        inject_advertisement(empty_device, empty_adv)
        assert len(detected) == 4


async def test_wrapped_instance_with_service_uuids(
    hass, mock_bleak_scanner_start, enable_bluetooth
):
    """Test consumers can use the wrapped instance with a service_uuids list as if it was normal BleakScanner."""
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=[]
    ):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init"):
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

        assert _get_manager() is not None
        scanner = models.HaBleakScannerWrapper(
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )
        scanner.register_detection_callback(_device_detected)

        for _ in range(2):
            inject_advertisement(switchbot_device, switchbot_adv)
            await hass.async_block_till_done()

        assert len(detected) == 2

        # The UUIDs list we created in the wrapped scanner with should be respected
        # and we should not get another callback
        inject_advertisement(empty_device, empty_adv)
        assert len(detected) == 2


async def test_wrapped_instance_with_broken_callbacks(
    hass, mock_bleak_scanner_start, enable_bluetooth
):
    """Test broken callbacks do not cause the scanner to fail."""
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=[]
    ), patch.object(hass.config_entries.flow, "async_init"):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init"):
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

        assert _get_manager() is not None
        scanner = models.HaBleakScannerWrapper(
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )
        scanner.register_detection_callback(_device_detected)

        inject_advertisement(switchbot_device, switchbot_adv)
        await hass.async_block_till_done()
        inject_advertisement(switchbot_device, switchbot_adv)
        await hass.async_block_till_done()
        assert len(detected) == 1


async def test_wrapped_instance_changes_uuids(
    hass, mock_bleak_scanner_start, enable_bluetooth
):
    """Test consumers can use the wrapped instance can change the uuids later."""
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=[]
    ):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init"):
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

        assert _get_manager() is not None
        scanner = models.HaBleakScannerWrapper()
        scanner.set_scanning_filter(
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )
        scanner.register_detection_callback(_device_detected)

        for _ in range(2):
            inject_advertisement(switchbot_device, switchbot_adv)
            await hass.async_block_till_done()

        assert len(detected) == 2

        # The UUIDs list we created in the wrapped scanner with should be respected
        # and we should not get another callback
        inject_advertisement(empty_device, empty_adv)
        assert len(detected) == 2


async def test_wrapped_instance_changes_filters(
    hass, mock_bleak_scanner_start, enable_bluetooth
):
    """Test consumers can use the wrapped instance can change the filter later."""
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=[]
    ):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        detected = []

        def _device_detected(
            device: BLEDevice, advertisement_data: AdvertisementData
        ) -> None:
            """Handle a detected device."""
            detected.append((device, advertisement_data))

        switchbot_device = BLEDevice("44:44:33:11:23:42", "wohand")
        switchbot_adv = AdvertisementData(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )
        empty_device = BLEDevice("11:22:33:44:55:62", "empty")
        empty_adv = AdvertisementData(local_name="empty")

        assert _get_manager() is not None
        scanner = models.HaBleakScannerWrapper()
        scanner.set_scanning_filter(
            filters={"UUIDs": ["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]}
        )
        scanner.register_detection_callback(_device_detected)

        for _ in range(2):
            inject_advertisement(switchbot_device, switchbot_adv)
            await hass.async_block_till_done()

        assert len(detected) == 2

        # The UUIDs list we created in the wrapped scanner with should be respected
        # and we should not get another callback
        inject_advertisement(empty_device, empty_adv)
        assert len(detected) == 2


async def test_wrapped_instance_unsupported_filter(
    hass, mock_bleak_scanner_start, caplog, enable_bluetooth
):
    """Test we want when their filter is ineffective."""
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=[]
    ):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert _get_manager() is not None
        scanner = models.HaBleakScannerWrapper()
        scanner.set_scanning_filter(
            filters={
                "unsupported": ["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
                "DuplicateData": True,
            }
        )
        assert "Only UUIDs filters are supported" in caplog.text


async def test_async_ble_device_from_address(
    hass, mock_bleak_scanner_start, macos_adapter
):
    """Test the async_ble_device_from_address api."""
    mock_bt = []
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch(
        "bleak.BleakScanner.discovered_devices",  # Must patch before we setup
        [MagicMock(address="44:44:33:11:23:45")],
    ):
        assert not bluetooth.async_discovered_service_info(hass)
        assert not bluetooth.async_address_present(hass, "44:44:22:22:11:22")
        assert (
            bluetooth.async_ble_device_from_address(hass, "44:44:33:11:23:45") is None
        )

        await async_setup_with_default_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        assert not bluetooth.async_discovered_service_info(hass)

        switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
        switchbot_adv = AdvertisementData(local_name="wohand", service_uuids=[])
        inject_advertisement(switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        assert (
            bluetooth.async_ble_device_from_address(hass, "44:44:33:11:23:45")
            is switchbot_device
        )

        assert (
            bluetooth.async_ble_device_from_address(hass, "00:66:33:22:11:22") is None
        )


async def test_can_unsetup_bluetooth_single_adapter_macos(
    hass, mock_bleak_scanner_start, enable_bluetooth, macos_adapter
):
    """Test we can setup and unsetup bluetooth."""
    entry = MockConfigEntry(domain=bluetooth.DOMAIN, data={}, unique_id=DEFAULT_ADDRESS)
    entry.add_to_hass(hass)

    for _ in range(2):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_can_unsetup_bluetooth_single_adapter_linux(
    hass, mock_bleak_scanner_start, enable_bluetooth, one_adapter
):
    """Test we can setup and unsetup bluetooth."""
    entry = MockConfigEntry(
        domain=bluetooth.DOMAIN, data={}, unique_id="00:00:00:00:00:01"
    )
    entry.add_to_hass(hass)

    for _ in range(2):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_can_unsetup_bluetooth_multiple_adapters(
    hass, mock_bleak_scanner_start, enable_bluetooth, two_adapters
):
    """Test we can setup and unsetup bluetooth with multiple adapters."""
    entry1 = MockConfigEntry(
        domain=bluetooth.DOMAIN, data={}, unique_id="00:00:00:00:00:01"
    )
    entry1.add_to_hass(hass)

    entry2 = MockConfigEntry(
        domain=bluetooth.DOMAIN, data={}, unique_id="00:00:00:00:00:02"
    )
    entry2.add_to_hass(hass)

    for _ in range(2):
        for entry in (entry1, entry2):
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()


async def test_three_adapters_one_missing(
    hass, mock_bleak_scanner_start, enable_bluetooth, two_adapters
):
    """Test three adapters but one is missing results in a retry on setup."""
    entry = MockConfigEntry(
        domain=bluetooth.DOMAIN, data={}, unique_id="00:00:00:00:00:03"
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_auto_detect_bluetooth_adapters_linux(hass, one_adapter):
    """Test we auto detect bluetooth adapters on linux."""
    assert await async_setup_component(hass, bluetooth.DOMAIN, {})
    await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(bluetooth.DOMAIN)
    assert len(hass.config_entries.flow.async_progress(bluetooth.DOMAIN)) == 1


async def test_auto_detect_bluetooth_adapters_linux_multiple(hass, two_adapters):
    """Test we auto detect bluetooth adapters on linux with multiple adapters."""
    assert await async_setup_component(hass, bluetooth.DOMAIN, {})
    await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(bluetooth.DOMAIN)
    assert len(hass.config_entries.flow.async_progress(bluetooth.DOMAIN)) == 2


async def test_auto_detect_bluetooth_adapters_linux_none_found(hass):
    """Test we auto detect bluetooth adapters on linux with no adapters found."""
    with patch(
        "bluetooth_adapters.get_bluetooth_adapter_details", return_value={}
    ), patch(
        "homeassistant.components.bluetooth.util.platform.system", return_value="Linux"
    ):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(bluetooth.DOMAIN)
    assert len(hass.config_entries.flow.async_progress(bluetooth.DOMAIN)) == 0


async def test_auto_detect_bluetooth_adapters_macos(hass):
    """Test we auto detect bluetooth adapters on macos."""
    with patch(
        "homeassistant.components.bluetooth.util.platform.system", return_value="Darwin"
    ):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(bluetooth.DOMAIN)
    assert len(hass.config_entries.flow.async_progress(bluetooth.DOMAIN)) == 1


async def test_no_auto_detect_bluetooth_adapters_windows(hass):
    """Test we auto detect bluetooth adapters on windows."""
    with patch(
        "homeassistant.components.bluetooth.util.platform.system",
        return_value="Windows",
    ):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(bluetooth.DOMAIN)
    assert len(hass.config_entries.flow.async_progress(bluetooth.DOMAIN)) == 0


async def test_getting_the_scanner_returns_the_wrapped_instance(hass, enable_bluetooth):
    """Test getting the scanner returns the wrapped instance."""
    scanner = bluetooth.async_get_scanner(hass)
    assert isinstance(scanner, models.HaBleakScannerWrapper)


async def test_migrate_single_entry_macos(
    hass, mock_bleak_scanner_start, macos_adapter
):
    """Test we can migrate a single entry on MacOS."""
    entry = MockConfigEntry(domain=bluetooth.DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, bluetooth.DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.unique_id == DEFAULT_ADDRESS


async def test_migrate_single_entry_linux(hass, mock_bleak_scanner_start, one_adapter):
    """Test we can migrate a single entry on Linux."""
    entry = MockConfigEntry(domain=bluetooth.DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, bluetooth.DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.unique_id == "00:00:00:00:00:01"
