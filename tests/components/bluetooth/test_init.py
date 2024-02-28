"""Tests for the Bluetooth integration."""
import asyncio
from datetime import timedelta
import time
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch

from bleak import BleakError
from bleak.backends.scanner import AdvertisementData, BLEDevice
from bluetooth_adapters import DEFAULT_ADDRESS
from habluetooth import scanner
from habluetooth.wrappers import HaBleakScannerWrapper
import pytest

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfo,
    async_process_advertisements,
    async_rediscover_address,
    async_track_unavailable,
)
from homeassistant.components.bluetooth.const import (
    BLUETOOTH_DISCOVERY_COOLDOWN_SECONDS,
    CONF_PASSIVE,
    DOMAIN,
    LINUX_FIRMWARE_LOAD_FALLBACK_SECONDS,
    SOURCE_LOCAL,
    UNAVAILABLE_TRACK_SECONDS,
)
from homeassistant.components.bluetooth.match import (
    ADDRESS,
    CONNECTABLE,
    LOCAL_NAME,
    MANUFACTURER_ID,
    SERVICE_DATA_UUID,
    SERVICE_UUID,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.issue_registry import async_get as async_get_issue_registry
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    FakeScanner,
    _get_manager,
    async_setup_with_default_adapter,
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement,
    inject_advertisement_with_time_and_source_connectable,
    patch_discovered_devices,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_and_stop(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
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


async def test_setup_and_stop_passive(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, one_adapter: None
) -> None:
    """Test we and setup and stop the scanner the passive scanner."""
    entry = MockConfigEntry(
        domain=bluetooth.DOMAIN,
        data={},
        options={CONF_PASSIVE: True},
        unique_id="00:00:00:00:00:01",
    )
    entry.add_to_hass(hass)
    init_kwargs = None

    class MockPassiveBleakScanner:
        def __init__(self, *args, **kwargs):
            """Init the scanner."""
            nonlocal init_kwargs
            init_kwargs = kwargs

        async def start(self, *args, **kwargs):
            """Start the scanner."""

        async def stop(self, *args, **kwargs):
            """Stop the scanner."""

        def register_detection_callback(self, *args, **kwargs):
            """Register a callback."""

    with patch(
        "habluetooth.scanner.OriginalBleakScanner",
        MockPassiveBleakScanner,
    ):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert init_kwargs == {
        "adapter": "hci0",
        "bluez": scanner.PASSIVE_SCANNER_ARGS,
        "scanning_mode": "passive",
        "detection_callback": ANY,
    }


async def test_setup_and_stop_old_bluez(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    one_adapter_old_bluez: None,
) -> None:
    """Test we and setup and stop the scanner the passive scanner with older bluez."""
    entry = MockConfigEntry(
        domain=bluetooth.DOMAIN,
        data={},
        options={},
        unique_id="00:00:00:00:00:01",
    )
    entry.add_to_hass(hass)
    init_kwargs = None

    class MockBleakScanner:
        def __init__(self, *args, **kwargs):
            """Init the scanner."""
            nonlocal init_kwargs
            init_kwargs = kwargs

        async def start(self, *args, **kwargs):
            """Start the scanner."""

        async def stop(self, *args, **kwargs):
            """Stop the scanner."""

        def register_detection_callback(self, *args, **kwargs):
            """Register a callback."""

    with patch(
        "habluetooth.scanner.OriginalBleakScanner",
        MockBleakScanner,
    ):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert init_kwargs == {
        "adapter": "hci0",
        "scanning_mode": "active",
        "detection_callback": ANY,
    }


async def test_setup_and_stop_no_bluetooth(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, macos_adapter: None
) -> None:
    """Test we fail gracefully when bluetooth is not available."""
    mock_bt = [
        {"domain": "switchbot", "service_uuid": "cba20d00-224d-11e6-9fb8-0002a5d5c51b"}
    ]
    with patch(
        "habluetooth.scanner.OriginalBleakScanner",
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


async def test_setup_and_stop_broken_bluetooth(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, macos_adapter: None
) -> None:
    """Test we fail gracefully when bluetooth/dbus is broken."""
    mock_bt = []
    with patch(
        "habluetooth.scanner.OriginalBleakScanner.start",
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


async def test_setup_and_stop_broken_bluetooth_hanging(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, macos_adapter: None
) -> None:
    """Test we fail gracefully when bluetooth/dbus is hanging."""
    mock_bt = []

    async def _mock_hang():
        await asyncio.sleep(1)

    with patch.object(scanner, "START_TIMEOUT", 0), patch(
        "habluetooth.scanner.OriginalBleakScanner.start",
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


async def test_setup_and_retry_adapter_not_yet_available(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, macos_adapter: None
) -> None:
    """Test we retry if the adapter is not yet available."""
    mock_bt = []
    with patch(
        "habluetooth.scanner.OriginalBleakScanner.start",
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
        "habluetooth.scanner.OriginalBleakScanner.start",
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
        await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    with patch(
        "habluetooth.scanner.OriginalBleakScanner.stop",
    ):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()


async def test_no_race_during_manual_reload_in_retry_state(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, macos_adapter: None
) -> None:
    """Test we can successfully reload when the entry is in a retry state."""
    mock_bt = []
    with patch(
        "habluetooth.scanner.OriginalBleakScanner.start",
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
        "habluetooth.scanner.OriginalBleakScanner.start",
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    with patch(
        "habluetooth.scanner.OriginalBleakScanner.stop",
    ):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()


async def test_calling_async_discovered_devices_no_bluetooth(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, macos_adapter: None
) -> None:
    """Test we fail gracefully when asking for discovered devices and there is no blueooth."""
    mock_bt = []
    with patch(
        "habluetooth.scanner.OriginalBleakScanner",
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
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
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

        wrong_device = generate_ble_device("44:44:33:11:23:45", "wrong_name")
        wrong_adv = generate_advertisement_data(
            local_name="wrong_name", service_uuids=[]
        )

        inject_advertisement(hass, wrong_device, wrong_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )

        inject_advertisement(hass, switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "switchbot"


@patch.object(
    bluetooth,
    "async_get_bluetooth",
    return_value=[
        {
            "domain": "sensorpush",
            "local_name": "s",
            "service_uuid": "ef090000-11d6-42ba-93b8-9dd7ec090aa9",
        }
    ],
)
async def test_discovery_match_by_service_uuid_and_short_local_name(
    mock_async_get_bluetooth: AsyncMock,
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
    """Test bluetooth discovery match by service_uuid and short local name."""
    entry = MockConfigEntry(domain="bluetooth", unique_id="00:00:00:00:00:01")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        await async_setup_with_default_adapter(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        wrong_device = generate_ble_device("44:44:33:11:23:45", "wrong_name")
        wrong_adv = generate_advertisement_data(local_name="s", service_uuids=[])

        inject_advertisement(hass, wrong_device, wrong_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0

        ht1_device = generate_ble_device("44:44:33:11:23:45", "s")
        ht1_adv = generate_advertisement_data(
            local_name="s", service_uuids=["ef090000-11d6-42ba-93b8-9dd7ec090aa9"]
        )

        inject_advertisement(hass, ht1_device, ht1_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "sensorpush"


def _domains_from_mock_config_flow(mock_config_flow: Mock) -> list[str]:
    """Get all the domains that were passed to async_init except bluetooth."""
    return [call[1][0] for call in mock_config_flow.mock_calls if call[1][0] != DOMAIN]


async def test_discovery_match_by_service_uuid_connectable(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
    """Test bluetooth discovery match by service_uuid and the ble device is connectable."""
    mock_bt = [
        {
            "domain": "switchbot",
            "connectable": True,
            "service_uuid": "cba20d00-224d-11e6-9fb8-0002a5d5c51b",
        }
    ]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        await async_setup_with_default_adapter(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        wrong_device = generate_ble_device("44:44:33:11:23:45", "wrong_name")
        wrong_adv = generate_advertisement_data(
            local_name="wrong_name", service_uuids=[]
        )

        inject_advertisement_with_time_and_source_connectable(
            hass, wrong_device, wrong_adv, time.monotonic(), "any", True
        )
        await hass.async_block_till_done()

        assert len(_domains_from_mock_config_flow(mock_config_flow)) == 0

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )

        inject_advertisement_with_time_and_source_connectable(
            hass, switchbot_device, switchbot_adv, time.monotonic(), "any", True
        )
        await hass.async_block_till_done()

        called_domains = _domains_from_mock_config_flow(mock_config_flow)
        assert len(called_domains) == 1
        assert called_domains == ["switchbot"]


async def test_discovery_match_by_service_uuid_not_connectable(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
    """Test bluetooth discovery match by service_uuid and the ble device is not connectable."""
    mock_bt = [
        {
            "domain": "switchbot",
            "connectable": True,
            "service_uuid": "cba20d00-224d-11e6-9fb8-0002a5d5c51b",
        }
    ]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        await async_setup_with_default_adapter(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        wrong_device = generate_ble_device("44:44:33:11:23:45", "wrong_name")
        wrong_adv = generate_advertisement_data(
            local_name="wrong_name", service_uuids=[]
        )

        inject_advertisement_with_time_and_source_connectable(
            hass, wrong_device, wrong_adv, time.monotonic(), "any", False
        )
        await hass.async_block_till_done()

        assert len(_domains_from_mock_config_flow(mock_config_flow)) == 0

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )

        inject_advertisement_with_time_and_source_connectable(
            hass, switchbot_device, switchbot_adv, time.monotonic(), "any", False
        )
        await hass.async_block_till_done()

        assert len(_domains_from_mock_config_flow(mock_config_flow)) == 0


async def test_discovery_match_by_name_connectable_false(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
    """Test bluetooth discovery match by name and the integration will take non-connectable devices."""
    mock_bt = [
        {
            "domain": "qingping",
            "connectable": False,
            "local_name": "Qingping*",
        }
    ]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        await async_setup_with_default_adapter(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        wrong_device = generate_ble_device("44:44:33:11:23:45", "wrong_name")
        wrong_adv = generate_advertisement_data(
            local_name="wrong_name", service_uuids=[]
        )

        inject_advertisement_with_time_and_source_connectable(
            hass, wrong_device, wrong_adv, time.monotonic(), "any", False
        )
        await hass.async_block_till_done()

        assert len(_domains_from_mock_config_flow(mock_config_flow)) == 0

        qingping_device = generate_ble_device(
            "44:44:33:11:23:45", "Qingping Motion & Light"
        )
        qingping_adv = generate_advertisement_data(
            local_name="Qingping Motion & Light",
            service_data={
                "0000fdcd-0000-1000-8000-00805f9b34fb": (
                    b"H\x12\xcd\xd5`4-X\x08\x04\x01\xe8\x00\x00\x0f\x01{"
                )
            },
        )

        inject_advertisement_with_time_and_source_connectable(
            hass, qingping_device, qingping_adv, time.monotonic(), "any", False
        )
        await hass.async_block_till_done()

        assert _domains_from_mock_config_flow(mock_config_flow) == ["qingping"]

        mock_config_flow.reset_mock()
        # Make sure it will also take a connectable device
        qingping_adv_with_better_rssi = generate_advertisement_data(
            local_name="Qingping Motion & Light",
            service_data={
                "0000fdcd-0000-1000-8000-00805f9b34fb": (
                    b"H\x12\xcd\xd5`4-X\x08\x04\x01\xe8\x00\x00\x0f\x02{"
                )
            },
            rssi=-30,
        )
        inject_advertisement_with_time_and_source_connectable(
            hass,
            qingping_device,
            qingping_adv_with_better_rssi,
            time.monotonic(),
            "any",
            True,
        )
        await hass.async_block_till_done()
        assert _domains_from_mock_config_flow(mock_config_flow) == ["qingping"]


async def test_discovery_match_by_local_name(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
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

        wrong_device = generate_ble_device("44:44:33:11:23:45", "wrong_name")
        wrong_adv = generate_advertisement_data(
            local_name="wrong_name", service_uuids=[]
        )

        inject_advertisement(hass, wrong_device, wrong_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand", service_uuids=[], manufacturer_data={1: b"\x01"}
        )

        inject_advertisement(hass, switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "switchbot"


async def test_discovery_match_by_manufacturer_id_and_manufacturer_data_start(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
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

        hkc_device = generate_ble_device("44:44:33:11:23:45", "lock")
        hkc_adv_no_mfr_data = generate_advertisement_data(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={},
        )
        hkc_adv = generate_advertisement_data(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={76: b"\x06\x02\x03\x99"},
        )

        # 1st discovery with no manufacturer data
        # should not trigger config flow
        inject_advertisement(hass, hkc_device, hkc_adv_no_mfr_data)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()

        # 2nd discovery with manufacturer data
        # should trigger a config flow
        inject_advertisement(hass, hkc_device, hkc_adv)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "homekit_controller"
        mock_config_flow.reset_mock()

        # 3rd discovery should not generate another flow
        inject_advertisement(hass, hkc_device, hkc_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0

        mock_config_flow.reset_mock()
        not_hkc_device = generate_ble_device("44:44:33:11:23:21", "lock")
        not_hkc_adv = generate_advertisement_data(
            local_name="lock", service_uuids=[], manufacturer_data={76: b"\x02"}
        )

        inject_advertisement(hass, not_hkc_device, not_hkc_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0
        not_apple_device = generate_ble_device("44:44:33:11:23:23", "lock")
        not_apple_adv = generate_advertisement_data(
            local_name="lock", service_uuids=[], manufacturer_data={21: b"\x02"}
        )

        inject_advertisement(hass, not_apple_device, not_apple_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0


async def test_discovery_match_by_service_data_uuid_then_others(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
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

        device = generate_ble_device("44:44:33:11:23:45", "lock")
        adv_without_service_data_uuid = generate_advertisement_data(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={},
        )
        adv_with_mfr_data = generate_advertisement_data(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={323: b"\x01\x02\x03"},
            service_data={},
        )
        adv_with_service_data_uuid = generate_advertisement_data(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={},
            service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"\x01\x02\x03"},
        )
        adv_with_service_data_uuid_and_mfr_data = generate_advertisement_data(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={323: b"\x01\x02\x03"},
            service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"\x01\x02\x03"},
        )
        adv_with_service_data_uuid_and_mfr_data_and_service_uuid = (
            generate_advertisement_data(
                local_name="lock",
                manufacturer_data={323: b"\x01\x02\x03"},
                service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"\x01\x02\x03"},
                service_uuids=["0000fd3d-0000-1000-8000-00805f9b34fd"],
            )
        )
        adv_with_service_uuid = generate_advertisement_data(
            local_name="lock",
            manufacturer_data={},
            service_data={},
            service_uuids=["0000fd3d-0000-1000-8000-00805f9b34fd"],
        )
        # 1st discovery should not generate a flow because the
        # service_data_uuid is not in the advertisement
        inject_advertisement(hass, device, adv_without_service_data_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()

        # 2nd discovery should not generate a flow because the
        # service_data_uuid is not in the advertisement
        inject_advertisement(hass, device, adv_without_service_data_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()

        # 3rd discovery should generate a flow because the
        # manufacturer_data is in the advertisement
        inject_advertisement(hass, device, adv_with_mfr_data)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "other_domain"
        mock_config_flow.reset_mock()

        # 4th discovery should generate a flow because the
        # service_data_uuid is in the advertisement and
        # we never saw a service_data_uuid before
        inject_advertisement(hass, device, adv_with_service_data_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "my_domain"
        mock_config_flow.reset_mock()

        # 5th discovery should not generate a flow because the
        # we already saw an advertisement with the service_data_uuid
        inject_advertisement(hass, device, adv_with_service_data_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0

        # 6th discovery should not generate a flow because the
        # manufacturer_data is in the advertisement
        # and we saw manufacturer_data before
        inject_advertisement(hass, device, adv_with_service_data_uuid_and_mfr_data)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()

        # 7th discovery should generate a flow because the
        # service_uuids is in the advertisement
        # and we never saw service_uuids before
        inject_advertisement(
            hass, device, adv_with_service_data_uuid_and_mfr_data_and_service_uuid
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
            hass, device, adv_with_service_data_uuid_and_mfr_data_and_service_uuid
        )
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()

        # 9th discovery should not generate a flow
        # since all fields have been seen at this point
        inject_advertisement(hass, device, adv_with_service_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0

        # 10th discovery should not generate a flow
        # since all fields have been seen at this point
        inject_advertisement(hass, device, adv_with_service_data_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0

        # 11th discovery should not generate a flow
        # since all fields have been seen at this point
        inject_advertisement(hass, device, adv_without_service_data_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0


async def test_discovery_match_by_service_data_uuid_when_format_changes(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
    """Test bluetooth discovery match by service_data_uuid when format changes."""
    mock_bt = [
        {
            "domain": "xiaomi_ble",
            "service_data_uuid": "0000fe95-0000-1000-8000-00805f9b34fb",
        },
        {
            "domain": "qingping",
            "service_data_uuid": "0000fdcd-0000-1000-8000-00805f9b34fb",
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

        device = generate_ble_device("44:44:33:11:23:45", "lock")
        adv_without_service_data_uuid = generate_advertisement_data(
            local_name="Qingping Temp RH M",
            service_uuids=[],
            manufacturer_data={},
        )
        xiaomi_format_adv = generate_advertisement_data(
            local_name="Qingping Temp RH M",
            service_data={
                "0000fe95-0000-1000-8000-00805f9b34fb": b"0XH\x0b\x06\xa7%\x144-X\x08"
            },
        )
        qingping_format_adv = generate_advertisement_data(
            local_name="Qingping Temp RH M",
            service_data={
                "0000fdcd-0000-1000-8000-00805f9b34fb": (
                    b"\x08\x16\xa7%\x144-X\x01\x04\xdb\x00\xa6\x01\x02\x01d"
                )
            },
        )
        # 1st discovery should not generate a flow because the
        # service_data_uuid is not in the advertisement
        inject_advertisement(hass, device, adv_without_service_data_uuid)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()

        # 2nd discovery should generate a flow because the
        # service_data_uuid matches xiaomi format
        inject_advertisement(hass, device, xiaomi_format_adv)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "xiaomi_ble"
        mock_config_flow.reset_mock()

        # 4th discovery should generate a flow because the
        # service_data_uuid matches qingping format
        inject_advertisement(hass, device, qingping_format_adv)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "qingping"
        mock_config_flow.reset_mock()

        # 5th discovery should not generate a flow because the
        # we already saw an advertisement with the service_data_uuid
        inject_advertisement(hass, device, qingping_format_adv)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()

        # 6th discovery should not generate a flow because the
        # we already saw an advertisement with the service_data_uuid
        inject_advertisement(hass, device, xiaomi_format_adv)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()


async def test_discovery_match_by_service_data_uuid_bthome(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
    """Test bluetooth discovery match by service_data_uuid for bthome."""
    mock_bt = [
        {
            "domain": "bthome",
            "service_data_uuid": "0000fcd2-0000-1000-8000-00805f9b34fb",
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

        device = generate_ble_device("44:44:33:11:23:45", "Shelly Button")
        button_adv = generate_advertisement_data(
            local_name="Shelly Button",
            service_uuids=[],
            manufacturer_data={},
            service_data={"0000fcd2-0000-1000-8000-00805f9b34fb": b"@\x00k\x01d:\x01"},
        )
        # 1st discovery should generate a flow because the service data uuid matches
        inject_advertisement(hass, device, button_adv)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1
        mock_config_flow.reset_mock()

        # 2nd discovery should not generate a flow because the
        # we already saw an advertisement with the service_data_uuid
        inject_advertisement(hass, device, button_adv)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0
        mock_config_flow.reset_mock()


async def test_discovery_match_first_by_service_uuid_and_then_manufacturer_id(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
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

        device = generate_ble_device("44:44:33:11:23:45", "lock")
        adv_service_uuids = generate_advertisement_data(
            local_name="lock",
            service_uuids=["0000fd3d-0000-1000-8000-00805f9b34fc"],
            manufacturer_data={},
        )
        adv_manufacturer_data = generate_advertisement_data(
            local_name="lock",
            service_uuids=[],
            manufacturer_data={76: b"\x06\x02\x03\x99"},
        )

        # 1st discovery with matches service_uuid
        # should trigger config flow
        inject_advertisement(hass, device, adv_service_uuids)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "my_domain"
        mock_config_flow.reset_mock()

        # 2nd discovery with manufacturer data
        # should trigger a config flow
        inject_advertisement(hass, device, adv_manufacturer_data)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "my_domain"
        mock_config_flow.reset_mock()

        # 3rd discovery should not generate another flow
        inject_advertisement(hass, device, adv_service_uuids)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0

        # 4th discovery should not generate another flow
        inject_advertisement(hass, device, adv_manufacturer_data)
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 0


async def test_rediscovery(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
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

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )
        switchbot_adv_2 = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={1: b"\x01"},
        )
        inject_advertisement(hass, switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        inject_advertisement(hass, switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "switchbot"

        async_rediscover_address(hass, "44:44:33:11:23:45")

        inject_advertisement(hass, switchbot_device, switchbot_adv_2)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 3
        assert mock_config_flow.mock_calls[1][1][0] == "switchbot"


async def test_async_discovered_device_api(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
    """Test the async_discovered_device API."""
    mock_bt = []
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch(
        "bleak.BleakScanner.discovered_devices_and_advertisement_data",  # Must patch before we setup
        {"44:44:33:11:23:45": (MagicMock(address="44:44:33:11:23:45"), MagicMock())},
    ):
        assert not bluetooth.async_discovered_service_info(hass)
        assert not bluetooth.async_address_present(hass, "44:44:22:22:11:22")
        await async_setup_with_default_adapter(hass)

        with patch.object(hass.config_entries.flow, "async_init"):
            hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
            await hass.async_block_till_done()

            assert len(mock_bleak_scanner_start.mock_calls) == 1

            assert not bluetooth.async_discovered_service_info(hass)

            wrong_device = generate_ble_device("44:44:33:11:23:42", "wrong_name")
            wrong_adv = generate_advertisement_data(
                local_name="wrong_name", service_uuids=[]
            )
            inject_advertisement(hass, wrong_device, wrong_adv)
            switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
            switchbot_adv = generate_advertisement_data(
                local_name="wohand", service_uuids=[]
            )
            inject_advertisement(hass, switchbot_device, switchbot_adv)
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
            inject_advertisement(hass, wrong_device, wrong_adv)
            inject_advertisement(hass, switchbot_device, switchbot_adv)
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
            infos = list(service_infos)
            assert infos[0].name == "wohand"
            assert infos[0].source == SOURCE_LOCAL
            assert isinstance(infos[0].device, BLEDevice)
            assert isinstance(infos[0].advertisement, AdvertisementData)

            assert bluetooth.async_address_present(hass, "44:44:33:11:23:42") is False
            assert bluetooth.async_address_present(hass, "44:44:33:11:23:45") is True


async def test_register_callbacks(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test registering a callback."""
    mock_bt = []
    callbacks = []

    def _fake_subscriber(
        service_info: BluetoothServiceInfo,
        change: BluetoothChange,
    ) -> None:
        """Fake subscriber for the BleakScanner."""
        callbacks.append((service_info, change))

    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch.object(hass.config_entries.flow, "async_init"):
        await async_setup_with_default_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        seen_switchbot_device = generate_ble_device("44:44:33:11:23:46", "wohand")
        seen_switchbot_adv = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )

        inject_advertisement(hass, seen_switchbot_device, seen_switchbot_adv)

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {SERVICE_UUID: "cba20d00-224d-11e6-9fb8-0002a5d5c51b"},
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )

        inject_advertisement(hass, switchbot_device, switchbot_adv)

        empty_device = generate_ble_device("11:22:33:44:55:66", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        inject_advertisement(hass, empty_device, empty_adv)
        await hass.async_block_till_done()

        empty_device = generate_ble_device("11:22:33:44:55:66", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        inject_advertisement(hass, empty_device, empty_adv)
        await hass.async_block_till_done()

        cancel()

        inject_advertisement(hass, empty_device, empty_adv)
        await hass.async_block_till_done()

    assert len(callbacks) == 2

    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "wohand"
    assert service_info.source == SOURCE_LOCAL
    assert service_info.manufacturer == "Nordic Semiconductor ASA"
    assert service_info.manufacturer_id == 89


async def test_register_callbacks_raises_exception(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    enable_bluetooth: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test registering a callback that raises ValueError."""
    mock_bt = []
    callbacks = []

    def _fake_subscriber(
        service_info: BluetoothServiceInfo,
        change: BluetoothChange,
    ) -> None:
        """Fake subscriber for the BleakScanner."""
        callbacks.append((service_info, change))
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
            {SERVICE_UUID: "cba20d00-224d-11e6-9fb8-0002a5d5c51b"},
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )

        inject_advertisement(hass, switchbot_device, switchbot_adv)

        cancel()

        inject_advertisement(hass, switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

    assert len(callbacks) == 1

    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "wohand"
    assert service_info.source == SOURCE_LOCAL
    assert service_info.manufacturer == "Nordic Semiconductor ASA"
    assert service_info.manufacturer_id == 89

    assert "ValueError" in caplog.text


async def test_register_callback_by_address(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
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

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )

        inject_advertisement(hass, switchbot_device, switchbot_adv)

        empty_device = generate_ble_device("11:22:33:44:55:66", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        inject_advertisement(hass, empty_device, empty_adv)
        await hass.async_block_till_done()

        empty_device = generate_ble_device("11:22:33:44:55:66", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        # 3rd callback raises ValueError but is still tracked
        inject_advertisement(hass, empty_device, empty_adv)
        await hass.async_block_till_done()

        cancel()

        # 4th callback should not be tracked since we canceled
        inject_advertisement(hass, empty_device, empty_adv)
        await hass.async_block_till_done()

        # Now register again with a callback that fails to
        # make sure we do not perm fail
        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {ADDRESS: "44:44:33:11:23:45"},
            BluetoothScanningMode.ACTIVE,
        )
        cancel()

        # Now register again, since the 3rd callback
        # should fail but we should still record it
        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {ADDRESS: "44:44:33:11:23:45"},
            BluetoothScanningMode.ACTIVE,
        )
        cancel()

    assert len(callbacks) == 3

    for idx in range(3):
        service_info: BluetoothServiceInfo = callbacks[idx][0]
        assert service_info.name == "wohand"
        assert service_info.manufacturer == "Nordic Semiconductor ASA"
        assert service_info.manufacturer_id == 89


async def test_register_callback_by_address_connectable_only(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test registering a callback by address connectable only."""
    mock_bt = []
    connectable_callbacks = []
    non_connectable_callbacks = []

    def _fake_connectable_subscriber(
        service_info: BluetoothServiceInfo, change: BluetoothChange
    ) -> None:
        """Fake subscriber for the BleakScanner."""
        connectable_callbacks.append((service_info, change))

    def _fake_non_connectable_subscriber(
        service_info: BluetoothServiceInfo, change: BluetoothChange
    ) -> None:
        """Fake subscriber for the BleakScanner."""
        non_connectable_callbacks.append((service_info, change))

    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_connectable_subscriber,
            {ADDRESS: "44:44:33:11:23:45", CONNECTABLE: True},
            BluetoothScanningMode.ACTIVE,
        )
        cancel2 = bluetooth.async_register_callback(
            hass,
            _fake_non_connectable_subscriber,
            {ADDRESS: "44:44:33:11:23:45", CONNECTABLE: False},
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )
        switchbot_adv_better_rssi = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x84"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
            rssi=-30,
        )
        inject_advertisement_with_time_and_source_connectable(
            hass, switchbot_device, switchbot_adv, time.monotonic(), "test", False
        )
        inject_advertisement_with_time_and_source_connectable(
            hass,
            switchbot_device,
            switchbot_adv_better_rssi,
            time.monotonic(),
            "test",
            True,
        )

        cancel()
        cancel2()

    assert len(connectable_callbacks) == 1
    # Non connectable will take either a connectable
    # or non-connectable device
    assert len(non_connectable_callbacks) == 2


async def test_register_callback_by_manufacturer_id(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test registering a callback by manufacturer_id."""
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

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {MANUFACTURER_ID: 21},
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        apple_device = generate_ble_device("44:44:33:11:23:45", "rtx")
        apple_adv = generate_advertisement_data(
            local_name="rtx",
            manufacturer_data={21: b"\xd8.\xad\xcd\r\x85"},
        )

        inject_advertisement(hass, apple_device, apple_adv)

        empty_device = generate_ble_device("11:22:33:44:55:66", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        inject_advertisement(hass, empty_device, empty_adv)
        await hass.async_block_till_done()

        cancel()

    assert len(callbacks) == 1

    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "rtx"
    assert service_info.manufacturer == "RTX Telecom A/S"
    assert service_info.manufacturer_id == 21


async def test_register_callback_by_connectable(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test registering a callback by connectable."""
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

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {CONNECTABLE: False},
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        apple_device = generate_ble_device("44:44:33:11:23:45", "rtx")
        apple_adv = generate_advertisement_data(
            local_name="rtx",
            manufacturer_data={7676: b"\xd8.\xad\xcd\r\x85"},
        )

        inject_advertisement(hass, apple_device, apple_adv)

        empty_device = generate_ble_device("11:22:33:44:55:66", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        inject_advertisement(hass, empty_device, empty_adv)
        await hass.async_block_till_done()

        cancel()

    assert len(callbacks) == 2

    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "rtx"
    service_info: BluetoothServiceInfo = callbacks[1][0]
    assert service_info.name == "empty"


async def test_not_filtering_wanted_apple_devices(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test filtering noisy apple devices."""
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

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {MANUFACTURER_ID: 76},
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        ibeacon_device = generate_ble_device("44:44:33:11:23:45", "rtx")
        ibeacon_adv = generate_advertisement_data(
            local_name="ibeacon",
            manufacturer_data={76: b"\x02\x00\x00\x00"},
        )

        inject_advertisement(hass, ibeacon_device, ibeacon_adv)

        homekit_device = generate_ble_device("44:44:33:11:23:46", "rtx")
        homekit_adv = generate_advertisement_data(
            local_name="homekit",
            manufacturer_data={76: b"\x06\x00\x00\x00"},
        )

        inject_advertisement(hass, homekit_device, homekit_adv)

        apple_device = generate_ble_device("44:44:33:11:23:47", "rtx")
        apple_adv = generate_advertisement_data(
            local_name="apple",
            manufacturer_data={76: b"\x10\x00\x00\x00"},
        )

        inject_advertisement(hass, apple_device, apple_adv)

        cancel()

    assert len(callbacks) == 3


async def test_filtering_noisy_apple_devices(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test filtering noisy apple devices."""
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

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {MANUFACTURER_ID: 21},
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        apple_device = generate_ble_device("44:44:33:11:23:45", "rtx")
        apple_adv = generate_advertisement_data(
            local_name="noisy",
            manufacturer_data={76: b"\xd8.\xad\xcd\r\x85"},
        )

        inject_advertisement(hass, apple_device, apple_adv)

        empty_device = generate_ble_device("11:22:33:44:55:66", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        inject_advertisement(hass, empty_device, empty_adv)
        await hass.async_block_till_done()

        cancel()

    assert len(callbacks) == 0


async def test_register_callback_by_address_connectable_manufacturer_id(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test registering a callback by address, manufacturer_id, and connectable."""
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

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {MANUFACTURER_ID: 21, CONNECTABLE: False, ADDRESS: "44:44:33:11:23:45"},
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        apple_device = generate_ble_device("44:44:33:11:23:45", "rtx")
        apple_adv = generate_advertisement_data(
            local_name="rtx",
            manufacturer_data={21: b"\xd8.\xad\xcd\r\x85"},
        )

        inject_advertisement(hass, apple_device, apple_adv)

        apple_device_wrong_address = generate_ble_device("44:44:33:11:23:46", "rtx")

        inject_advertisement(hass, apple_device_wrong_address, apple_adv)
        await hass.async_block_till_done()

        cancel()

    assert len(callbacks) == 1

    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "rtx"
    assert service_info.manufacturer == "RTX Telecom A/S"
    assert service_info.manufacturer_id == 21


async def test_register_callback_by_manufacturer_id_and_address(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test registering a callback by manufacturer_id and address."""
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

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {MANUFACTURER_ID: 21, ADDRESS: "44:44:33:11:23:45"},
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        rtx_device = generate_ble_device("44:44:33:11:23:45", "rtx")
        rtx_adv = generate_advertisement_data(
            local_name="rtx",
            manufacturer_data={21: b"\xd8.\xad\xcd\r\x85"},
        )

        inject_advertisement(hass, rtx_device, rtx_adv)

        yale_device = generate_ble_device("44:44:33:11:23:45", "apple")
        yale_adv = generate_advertisement_data(
            local_name="yale",
            manufacturer_data={465: b"\xd8.\xad\xcd\r\x85"},
        )

        inject_advertisement(hass, yale_device, yale_adv)
        await hass.async_block_till_done()

        other_apple_device = generate_ble_device("44:44:33:11:23:22", "apple")
        other_apple_adv = generate_advertisement_data(
            local_name="apple",
            manufacturer_data={21: b"\xd8.\xad\xcd\r\x85"},
        )
        inject_advertisement(hass, other_apple_device, other_apple_adv)

        cancel()

    assert len(callbacks) == 1

    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "rtx"
    assert service_info.manufacturer == "RTX Telecom A/S"
    assert service_info.manufacturer_id == 21


async def test_register_callback_by_service_uuid_and_address(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test registering a callback by service_uuid and address."""
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

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {
                SERVICE_UUID: "cba20d00-224d-11e6-9fb8-0002a5d5c51b",
                ADDRESS: "44:44:33:11:23:45",
            },
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        switchbot_dev = generate_ble_device("44:44:33:11:23:45", "switchbot")
        switchbot_adv = generate_advertisement_data(
            local_name="switchbot",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        )

        inject_advertisement(hass, switchbot_dev, switchbot_adv)

        switchbot_missing_service_uuid_dev = generate_ble_device(
            "44:44:33:11:23:45", "switchbot"
        )
        switchbot_missing_service_uuid_adv = generate_advertisement_data(
            local_name="switchbot",
        )

        inject_advertisement(
            hass, switchbot_missing_service_uuid_dev, switchbot_missing_service_uuid_adv
        )
        await hass.async_block_till_done()

        service_uuid_wrong_address_dev = generate_ble_device(
            "44:44:33:11:23:22", "switchbot2"
        )
        service_uuid_wrong_address_adv = generate_advertisement_data(
            local_name="switchbot2",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        )
        inject_advertisement(
            hass, service_uuid_wrong_address_dev, service_uuid_wrong_address_adv
        )

        cancel()

    assert len(callbacks) == 1

    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "switchbot"


async def test_register_callback_by_service_data_uuid_and_address(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test registering a callback by service_data_uuid and address."""
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

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {
                SERVICE_DATA_UUID: "cba20d00-224d-11e6-9fb8-0002a5d5c51b",
                ADDRESS: "44:44:33:11:23:45",
            },
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        switchbot_dev = generate_ble_device("44:44:33:11:23:45", "switchbot")
        switchbot_adv = generate_advertisement_data(
            local_name="switchbot",
            service_data={"cba20d00-224d-11e6-9fb8-0002a5d5c51b": b"x"},
        )

        inject_advertisement(hass, switchbot_dev, switchbot_adv)

        switchbot_missing_service_uuid_dev = generate_ble_device(
            "44:44:33:11:23:45", "switchbot"
        )
        switchbot_missing_service_uuid_adv = generate_advertisement_data(
            local_name="switchbot",
        )

        inject_advertisement(
            hass, switchbot_missing_service_uuid_dev, switchbot_missing_service_uuid_adv
        )
        await hass.async_block_till_done()

        service_uuid_wrong_address_dev = generate_ble_device(
            "44:44:33:11:23:22", "switchbot2"
        )
        service_uuid_wrong_address_adv = generate_advertisement_data(
            local_name="switchbot2",
            service_data={"cba20d00-224d-11e6-9fb8-0002a5d5c51b": b"x"},
        )
        inject_advertisement(
            hass, service_uuid_wrong_address_dev, service_uuid_wrong_address_adv
        )

        cancel()

    assert len(callbacks) == 1

    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "switchbot"


async def test_register_callback_by_local_name(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test registering a callback by local_name."""
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

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {LOCAL_NAME: "rtx"},
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        rtx_device = generate_ble_device("44:44:33:11:23:45", "rtx")
        rtx_adv = generate_advertisement_data(
            local_name="rtx",
            manufacturer_data={21: b"\xd8.\xad\xcd\r\x85"},
        )

        inject_advertisement(hass, rtx_device, rtx_adv)

        empty_device = generate_ble_device("11:22:33:44:55:66", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        inject_advertisement(hass, empty_device, empty_adv)

        rtx_device_2 = generate_ble_device("44:44:33:11:23:45", "rtx")
        rtx_adv_2 = generate_advertisement_data(
            local_name="rtx2",
            manufacturer_data={21: b"\xd8.\xad\xcd\r\x85"},
        )
        inject_advertisement(hass, rtx_device_2, rtx_adv_2)

        await hass.async_block_till_done()

        cancel()

    assert len(callbacks) == 1

    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "rtx"
    assert service_info.manufacturer == "RTX Telecom A/S"
    assert service_info.manufacturer_id == 21


async def test_register_callback_by_local_name_overly_broad(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    enable_bluetooth: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test registering a callback by local_name that is too broad."""
    mock_bt = []

    def _fake_subscriber(
        service_info: BluetoothServiceInfo, change: BluetoothChange
    ) -> None:
        """Fake subscriber for the BleakScanner."""

    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        await async_setup_with_default_adapter(hass)

    with pytest.raises(ValueError):
        bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {LOCAL_NAME: "ab*"},
            BluetoothScanningMode.ACTIVE,
        )


async def test_register_callback_by_service_data_uuid(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test registering a callback by service_data_uuid."""
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

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = bluetooth.async_register_callback(
            hass,
            _fake_subscriber,
            {SERVICE_DATA_UUID: "0000fe95-0000-1000-8000-00805f9b34fb"},
            BluetoothScanningMode.ACTIVE,
        )

        assert len(mock_bleak_scanner_start.mock_calls) == 1

        apple_device = generate_ble_device("44:44:33:11:23:45", "xiaomi")
        apple_adv = generate_advertisement_data(
            local_name="xiaomi",
            service_data={
                "0000fe95-0000-1000-8000-00805f9b34fb": b"\xd8.\xad\xcd\r\x85"
            },
        )

        inject_advertisement(hass, apple_device, apple_adv)

        empty_device = generate_ble_device("11:22:33:44:55:66", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        inject_advertisement(hass, empty_device, empty_adv)
        await hass.async_block_till_done()

        cancel()

    assert len(callbacks) == 1

    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "xiaomi"


async def test_register_callback_survives_reload(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
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

    cancel = bluetooth.async_register_callback(
        hass,
        _fake_subscriber,
        {"address": "44:44:33:11:23:45"},
        BluetoothScanningMode.ACTIVE,
    )

    assert len(mock_bleak_scanner_start.mock_calls) == 1

    switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
    switchbot_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=["zba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
    )
    switchbot_adv_2 = generate_advertisement_data(
        local_name="wohand",
        service_uuids=["zba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        manufacturer_data={89: b"\xd8.\xad\xcd\r\x84"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
    )
    inject_advertisement(hass, switchbot_device, switchbot_adv)
    assert len(callbacks) == 1
    service_info: BluetoothServiceInfo = callbacks[0][0]
    assert service_info.name == "wohand"
    assert service_info.manufacturer == "Nordic Semiconductor ASA"
    assert service_info.manufacturer_id == 89

    entry = hass.config_entries.async_entries(bluetooth.DOMAIN)[0]
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    inject_advertisement(hass, switchbot_device, switchbot_adv_2)
    assert len(callbacks) == 2
    service_info: BluetoothServiceInfo = callbacks[1][0]
    assert service_info.name == "wohand"
    assert service_info.manufacturer == "Nordic Semiconductor ASA"
    assert service_info.manufacturer_id == 89
    cancel()


async def test_process_advertisements_bail_on_good_advertisement(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
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
        device = generate_ble_device("aa:44:33:11:23:45", "wohand")
        adv = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51a"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fa": b"H\x10c"},
        )

        inject_advertisement(hass, device, adv)
        inject_advertisement(hass, device, adv)
        inject_advertisement(hass, device, adv)

        await asyncio.sleep(0)

    result = await handle
    assert result.name == "wohand"


async def test_process_advertisements_ignore_bad_advertisement(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Check that we ignore bad advertisements."""
    done = asyncio.Event()
    return_value = asyncio.Event()

    device = generate_ble_device("aa:44:33:11:23:45", "wohand")
    adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51a"],
        manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fa": b""},
    )
    adv2 = generate_advertisement_data(
        local_name="wohand",
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51a"],
        manufacturer_data={89: b"\xd8.\xad\xcd\r\x84"},
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
        inject_advertisement(hass, device, adv)
        inject_advertisement(hass, device, adv2)
        await asyncio.sleep(0)

    # Set the return value and mutate the advertisement
    # Check that scan ends and correct advertisement data is returned
    return_value.set()
    adv.service_data["00000d00-0000-1000-8000-00805f9b34fa"] = b"H\x10c"
    inject_advertisement(hass, device, adv)
    inject_advertisement(hass, device, adv2)
    await asyncio.sleep(0)

    result = await handle
    assert result.service_data["00000d00-0000-1000-8000-00805f9b34fa"] == b"H\x10c"


async def test_process_advertisements_timeout(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test we timeout if no advertisements at all."""

    def _callback(service_info: BluetoothServiceInfo) -> bool:
        return False

    with pytest.raises(TimeoutError):
        await async_process_advertisements(
            hass, _callback, {}, BluetoothScanningMode.ACTIVE, 0
        )


async def test_wrapped_instance_with_filter(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
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

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )
        switchbot_adv_2 = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x84"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )
        empty_device = generate_ble_device("11:22:33:44:55:66", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        assert _get_manager() is not None
        scanner = HaBleakScannerWrapper(
            filters={"UUIDs": ["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]}
        )
        scanner.register_detection_callback(_device_detected)

        inject_advertisement(hass, switchbot_device, switchbot_adv_2)
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

        inject_advertisement(hass, switchbot_device, switchbot_adv)
        assert len(detected) == 4

        # The filter we created in the wrapped scanner with should be respected
        # and we should not get another callback
        inject_advertisement(hass, empty_device, empty_adv)
        assert len(detected) == 4


async def test_wrapped_instance_with_service_uuids(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
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

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )
        switchbot_adv_2 = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x84"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )
        empty_device = generate_ble_device("11:22:33:44:55:66", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        assert _get_manager() is not None
        scanner = HaBleakScannerWrapper(
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )
        scanner.register_detection_callback(_device_detected)

        inject_advertisement(hass, switchbot_device, switchbot_adv)
        inject_advertisement(hass, switchbot_device, switchbot_adv_2)

        await hass.async_block_till_done()

        assert len(detected) == 2

        # The UUIDs list we created in the wrapped scanner with should be respected
        # and we should not get another callback
        inject_advertisement(hass, empty_device, empty_adv)
        assert len(detected) == 2


async def test_wrapped_instance_with_service_uuids_with_coro_callback(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
    """Test consumers can use the wrapped instance with a service_uuids list as if it was normal BleakScanner.

    Verify that coro callbacks are supported.
    """
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=[]
    ):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        detected = []

        async def _device_detected(
            device: BLEDevice, advertisement_data: AdvertisementData
        ) -> None:
            """Handle a detected device."""
            detected.append((device, advertisement_data))

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )
        switchbot_adv_2 = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x84"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )
        empty_device = generate_ble_device("11:22:33:44:55:66", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        assert _get_manager() is not None
        scanner = HaBleakScannerWrapper(
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )
        scanner.register_detection_callback(_device_detected)

        inject_advertisement(hass, switchbot_device, switchbot_adv)
        inject_advertisement(hass, switchbot_device, switchbot_adv_2)

        await hass.async_block_till_done()

        assert len(detected) == 2

        # The UUIDs list we created in the wrapped scanner with should be respected
        # and we should not get another callback
        inject_advertisement(hass, empty_device, empty_adv)
        assert len(detected) == 2


async def test_wrapped_instance_with_broken_callbacks(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
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

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )

        assert _get_manager() is not None
        scanner = HaBleakScannerWrapper(
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )
        scanner.register_detection_callback(_device_detected)

        inject_advertisement(hass, switchbot_device, switchbot_adv)
        await hass.async_block_till_done()
        inject_advertisement(hass, switchbot_device, switchbot_adv)
        await hass.async_block_till_done()
        assert len(detected) == 1


async def test_wrapped_instance_changes_uuids(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
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

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )
        switchbot_adv_2 = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x84"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )
        empty_device = generate_ble_device("11:22:33:44:55:66", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        assert _get_manager() is not None
        scanner = HaBleakScannerWrapper()
        scanner.set_scanning_filter(
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
        )
        scanner.register_detection_callback(_device_detected)

        inject_advertisement(hass, switchbot_device, switchbot_adv)
        inject_advertisement(hass, switchbot_device, switchbot_adv_2)
        await hass.async_block_till_done()

        assert len(detected) == 2

        # The UUIDs list we created in the wrapped scanner with should be respected
        # and we should not get another callback
        inject_advertisement(hass, empty_device, empty_adv)
        assert len(detected) == 2


async def test_wrapped_instance_changes_filters(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, enable_bluetooth: None
) -> None:
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

        switchbot_device = generate_ble_device("44:44:33:11:23:42", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )
        switchbot_adv_2 = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
            manufacturer_data={89: b"\xd8.\xad\xcd\r\x84"},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x10c"},
        )
        empty_device = generate_ble_device("11:22:33:44:55:62", "empty")
        empty_adv = generate_advertisement_data(local_name="empty")

        assert _get_manager() is not None
        scanner = HaBleakScannerWrapper()
        scanner.set_scanning_filter(
            filters={"UUIDs": ["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]}
        )
        scanner.register_detection_callback(_device_detected)

        inject_advertisement(hass, switchbot_device, switchbot_adv)
        inject_advertisement(hass, switchbot_device, switchbot_adv_2)

        await hass.async_block_till_done()

        assert len(detected) == 2

        # The UUIDs list we created in the wrapped scanner with should be respected
        # and we should not get another callback
        inject_advertisement(hass, empty_device, empty_adv)
        assert len(detected) == 2


async def test_wrapped_instance_unsupported_filter(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    caplog: pytest.LogCaptureFixture,
    enable_bluetooth: None,
) -> None:
    """Test we want when their filter is ineffective."""
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=[]
    ):
        await async_setup_with_default_adapter(hass)

    with patch.object(hass.config_entries.flow, "async_init"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert _get_manager() is not None
        scanner = HaBleakScannerWrapper()
        scanner.set_scanning_filter(
            filters={
                "unsupported": ["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
                "DuplicateData": True,
            }
        )
        assert "Only UUIDs filters are supported" in caplog.text


async def test_async_ble_device_from_address(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
    """Test the async_ble_device_from_address api."""
    mock_bt = []
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ), patch(
        "bleak.BleakScanner.discovered_devices_and_advertisement_data",  # Must patch before we setup
        {"44:44:33:11:23:45": (MagicMock(address="44:44:33:11:23:45"), MagicMock())},
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

        switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
        switchbot_adv = generate_advertisement_data(
            local_name="wohand", service_uuids=[]
        )
        inject_advertisement(hass, switchbot_device, switchbot_adv)
        await hass.async_block_till_done()

        assert (
            bluetooth.async_ble_device_from_address(hass, "44:44:33:11:23:45")
            is switchbot_device
        )

        assert (
            bluetooth.async_ble_device_from_address(hass, "00:66:33:22:11:22") is None
        )


async def test_can_unsetup_bluetooth_single_adapter_macos(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
    """Test we can setup and unsetup bluetooth."""
    entry = MockConfigEntry(domain=bluetooth.DOMAIN, data={}, unique_id=DEFAULT_ADDRESS)
    entry.add_to_hass(hass)

    for _ in range(2):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_can_unsetup_bluetooth_single_adapter_linux(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    enable_bluetooth: None,
    one_adapter: None,
) -> None:
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
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    enable_bluetooth: None,
    two_adapters: None,
) -> None:
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
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    enable_bluetooth: None,
    two_adapters: None,
) -> None:
    """Test three adapters but one is missing results in a retry on setup."""
    entry = MockConfigEntry(
        domain=bluetooth.DOMAIN, data={}, unique_id="00:00:00:00:00:03"
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_auto_detect_bluetooth_adapters_linux(
    hass: HomeAssistant, one_adapter: None
) -> None:
    """Test we auto detect bluetooth adapters on linux."""
    assert await async_setup_component(hass, bluetooth.DOMAIN, {})
    await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(bluetooth.DOMAIN)
    assert len(hass.config_entries.flow.async_progress(bluetooth.DOMAIN)) == 1


async def test_auto_detect_bluetooth_adapters_linux_multiple(
    hass: HomeAssistant, two_adapters: None
) -> None:
    """Test we auto detect bluetooth adapters on linux with multiple adapters."""
    assert await async_setup_component(hass, bluetooth.DOMAIN, {})
    await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(bluetooth.DOMAIN)
    assert len(hass.config_entries.flow.async_progress(bluetooth.DOMAIN)) == 2


async def test_auto_detect_bluetooth_adapters_linux_none_found(
    hass: HomeAssistant,
) -> None:
    """Test we auto detect bluetooth adapters on linux with no adapters found."""
    with patch(
        "bluetooth_adapters.systems.platform.system", return_value="Linux"
    ), patch("bluetooth_adapters.systems.linux.LinuxAdapters.refresh"), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.adapters",
        {},
    ):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(bluetooth.DOMAIN)
    assert len(hass.config_entries.flow.async_progress(bluetooth.DOMAIN)) == 0


async def test_auto_detect_bluetooth_adapters_macos(hass: HomeAssistant) -> None:
    """Test we auto detect bluetooth adapters on macos."""
    with patch("bluetooth_adapters.systems.platform.system", return_value="Darwin"):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(bluetooth.DOMAIN)
    assert len(hass.config_entries.flow.async_progress(bluetooth.DOMAIN)) == 1


async def test_no_auto_detect_bluetooth_adapters_windows(hass: HomeAssistant) -> None:
    """Test we auto detect bluetooth adapters on windows."""
    with patch(
        "bluetooth_adapters.systems.platform.system",
        return_value="Windows",
    ):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(bluetooth.DOMAIN)
    assert len(hass.config_entries.flow.async_progress(bluetooth.DOMAIN)) == 0


async def test_getting_the_scanner_returns_the_wrapped_instance(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test getting the scanner returns the wrapped instance."""
    scanner = bluetooth.async_get_scanner(hass)
    assert isinstance(scanner, HaBleakScannerWrapper)


async def test_scanner_count_connectable(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test getting the connectable scanner count."""
    scanner = FakeScanner("any", "any")
    cancel = bluetooth.async_register_scanner(hass, scanner)
    assert bluetooth.async_scanner_count(hass, connectable=True) == 1
    cancel()


async def test_scanner_count(hass: HomeAssistant, enable_bluetooth: None) -> None:
    """Test getting the connectable and non-connectable scanner count."""
    scanner = FakeScanner("any", "any")
    cancel = bluetooth.async_register_scanner(hass, scanner)
    assert bluetooth.async_scanner_count(hass, connectable=False) == 2
    cancel()


async def test_migrate_single_entry_macos(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
    """Test we can migrate a single entry on MacOS."""
    entry = MockConfigEntry(domain=bluetooth.DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, bluetooth.DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.unique_id == DEFAULT_ADDRESS


async def test_migrate_single_entry_linux(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, one_adapter: None
) -> None:
    """Test we can migrate a single entry on Linux."""
    entry = MockConfigEntry(domain=bluetooth.DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, bluetooth.DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.unique_id == "00:00:00:00:00:01"


async def test_discover_new_usb_adapters(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, one_adapter: None
) -> None:
    """Test we can discover new usb adapters."""
    entry = MockConfigEntry(
        domain=bluetooth.DOMAIN, data={}, unique_id="00:00:00:00:00:01"
    )
    entry.add_to_hass(hass)

    saved_callback = None

    def _async_register_scan_request_callback(_hass, _callback):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.usb.async_register_scan_request_callback",
        _async_register_scan_request_callback,
    ):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()

    assert not hass.config_entries.flow.async_progress(DOMAIN)

    saved_callback()
    assert not hass.config_entries.flow.async_progress(DOMAIN)

    with patch(
        "bluetooth_adapters.systems.platform.system", return_value="Linux"
    ), patch("bluetooth_adapters.systems.linux.LinuxAdapters.refresh"), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.adapters",
        {
            "hci0": {
                "address": "00:00:00:00:00:01",
                "hw_version": "usb:v1D6Bp0246d053F",
                "passive_scan": False,
                "sw_version": "homeassistant",
            },
            "hci1": {
                "address": "00:00:00:00:00:02",
                "hw_version": "usb:v1D6Bp0246d053F",
                "passive_scan": False,
                "sw_version": "homeassistant",
            },
        },
    ):
        for wait_sec in range(10, 20):
            async_fire_time_changed(
                hass, dt_util.utcnow() + timedelta(seconds=wait_sec)
            )
            await hass.async_block_till_done()

    assert len(hass.config_entries.flow.async_progress(DOMAIN)) == 1


async def test_discover_new_usb_adapters_with_firmware_fallback_delay(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, one_adapter: None
) -> None:
    """Test we can discover new usb adapters with a firmware fallback delay."""
    entry = MockConfigEntry(
        domain=bluetooth.DOMAIN, data={}, unique_id="00:00:00:00:00:01"
    )
    entry.add_to_hass(hass)

    saved_callback = None

    def _async_register_scan_request_callback(_hass, _callback):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.usb.async_register_scan_request_callback",
        _async_register_scan_request_callback,
    ):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()

    assert not hass.config_entries.flow.async_progress(DOMAIN)

    saved_callback()
    assert not hass.config_entries.flow.async_progress(DOMAIN)

    with patch(
        "bluetooth_adapters.systems.platform.system", return_value="Linux"
    ), patch("bluetooth_adapters.systems.linux.LinuxAdapters.refresh"), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.adapters",
        {},
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(BLUETOOTH_DISCOVERY_COOLDOWN_SECONDS * 2)
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.flow.async_progress(DOMAIN)) == 0

    with patch(
        "bluetooth_adapters.systems.platform.system", return_value="Linux"
    ), patch("bluetooth_adapters.systems.linux.LinuxAdapters.refresh"), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.adapters",
        {
            "hci0": {
                "address": "00:00:00:00:00:01",
                "hw_version": "usb:v1D6Bp0246d053F",
                "passive_scan": False,
                "sw_version": "homeassistant",
            },
            "hci1": {
                "address": "00:00:00:00:00:02",
                "hw_version": "usb:v1D6Bp0246d053F",
                "passive_scan": False,
                "sw_version": "homeassistant",
            },
        },
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(
                seconds=LINUX_FIRMWARE_LOAD_FALLBACK_SECONDS
                + (BLUETOOTH_DISCOVERY_COOLDOWN_SECONDS * 2)
            ),
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.flow.async_progress(DOMAIN)) == 1


async def test_issue_outdated_haos_removed(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    no_adapters: None,
    operating_system_85: None,
) -> None:
    """Test we do not create an issue on outdated haos anymore."""
    assert await async_setup_component(hass, bluetooth.DOMAIN, {})
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    registry = async_get_issue_registry(hass)
    issue = registry.async_get_issue(DOMAIN, "haos_outdated")
    assert issue is None


async def test_haos_9_or_later(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    one_adapter: None,
    operating_system_90: None,
) -> None:
    """Test we do not create issues for haos 9.x or later."""
    entry = MockConfigEntry(
        domain=bluetooth.DOMAIN, data={}, unique_id="00:00:00:00:00:01"
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, bluetooth.DOMAIN, {})
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    registry = async_get_issue_registry(hass)
    issue = registry.async_get_issue(DOMAIN, "haos_outdated")
    assert issue is None
