"""Fixtures for Pinecil tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
from habluetooth import BluetoothServiceInfoBleak
from pynecil import (
    AnimationSpeed,
    AutostartMode,
    BatteryType,
    DeviceInfoResponse,
    LatestRelease,
    LiveDataResponse,
    LockingMode,
    LogoDuration,
    OperatingMode,
    PowerSource,
    ScreenOrientationMode,
    ScrollSpeed,
    SettingsDataResponse,
    TempUnit,
    TipType,
)
import pytest

from homeassistant.components.iron_os import DOMAIN
from homeassistant.config_entries import SOURCE_IGNORE
from homeassistant.const import CONF_ADDRESS

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

USER_INPUT = {CONF_ADDRESS: "c0:ff:ee:c0:ff:ee"}
DEFAULT_NAME = "Pinecil-C0FFEEE"
PINECIL_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Pinecil-C0FFEEE",
    address="c0:ff:ee:c0:ff:ee",
    device=generate_ble_device(
        address="c0:ff:ee:c0:ff:ee",
        name="Pinecil-C0FFEEE",
    ),
    rssi=-61,
    manufacturer_data={},
    service_data={},
    service_uuids=["9eae1000-9d0d-48c5-aa55-33e27f9bc533"],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={},
        service_uuids=["9eae1000-9d0d-48c5-aa55-33e27f9bc533"],
    ),
    connectable=True,
    time=0,
    tx_power=None,
)

UNKNOWN_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="",
    address="c0:ff:ee:c0:ff:ee",
    device=generate_ble_device(
        address="c0:ff:ee:c0:ff:ee",
        name="",
    ),
    rssi=-61,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={},
        service_uuids=[],
    ),
    connectable=True,
    time=0,
    tx_power=None,
)


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.iron_os.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="discovery")
def mock_async_discovered_service_info() -> Generator[MagicMock]:
    """Mock service discovery."""
    with patch(
        "homeassistant.components.iron_os.config_flow.async_discovered_service_info",
        return_value=[PINECIL_SERVICE_INFO, UNKNOWN_SERVICE_INFO],
    ) as discovery:
        yield discovery


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Pinecil configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={},
        unique_id="c0:ff:ee:c0:ff:ee",
        entry_id="1234567890",
    )


@pytest.fixture(name="config_entry_ignored")
def mock_config_entry_ignored() -> MockConfigEntry:
    """Mock Pinecil configuration entry for ignored device."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={},
        unique_id="c0:ff:ee:c0:ff:ee",
        entry_id="1234567890",
        source=SOURCE_IGNORE,
    )


@pytest.fixture(name="ble_device")
def mock_ble_device() -> Generator[MagicMock]:
    """Mock BLEDevice."""
    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=BLEDevice(
            address="c0:ff:ee:c0:ff:ee", name=DEFAULT_NAME, rssi=-50, details={}
        ),
    ) as ble_device:
        yield ble_device


@pytest.fixture(autouse=True)
def mock_ironosupdate() -> Generator[AsyncMock]:
    """Mock IronOSUpdate."""

    with patch(
        "homeassistant.components.iron_os.IronOSUpdate",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.latest_release.return_value = LatestRelease(
            html_url="https://github.com/Ralim/IronOS/releases/tag/v2.22",
            name="V2.22 | TS101 & S60 Added | PinecilV2 improved",
            tag_name="v2.22",
            body="**RELEASE_NOTES**",
        )

        yield client


@pytest.fixture
def mock_pynecil() -> Generator[AsyncMock]:
    """Mock Pynecil library."""
    with patch(
        "homeassistant.components.iron_os.Pynecil", autospec=True
    ) as mock_client:
        client = mock_client.return_value

        client.get_device_info.return_value = DeviceInfoResponse(
            build="v2.23",
            device_id="c0ffeeC0",
            address="c0:ff:ee:c0:ff:ee",
            device_sn="0000c0ffeec0ffee",
            name=DEFAULT_NAME,
        )
        client.get_settings.return_value = SettingsDataResponse(
            sleep_temp=150,
            sleep_timeout=5,
            min_dc_voltage_cells=BatteryType.BATTERY_3S,
            min_volltage_per_cell=3.3,
            qc_ideal_voltage=9.0,
            accel_sensitivity=7,
            shutdown_time=10,
            keep_awake_pulse_power=0.5,
            keep_awake_pulse_delay=4,
            keep_awake_pulse_duration=1,
            voltage_div=600,
            boost_temp=420,
            calibration_offset=900,
            power_limit=12.0,
            temp_increment_long=10,
            temp_increment_short=1,
            hall_sensitivity=7,
            pd_negotiation_timeout=2.0,
            display_brightness=3,
            orientation_mode=ScreenOrientationMode.RIGHT_HANDED,
            animation_speed=AnimationSpeed.MEDIUM,
            autostart_mode=AutostartMode.IDLE,
            temp_unit=TempUnit.CELSIUS,
            desc_scroll_speed=ScrollSpeed.FAST,
            logo_duration=LogoDuration.LOOP,
            locking_mode=LockingMode.FULL_LOCKING,
            animation_loop=True,
            cooling_temp_blink=True,
            idle_screen_details=True,
            solder_screen_details=True,
            invert_buttons=True,
            display_invert=True,
            calibrate_cjc=True,
            usb_pd_mode=True,
            hall_sleep_time=5,
            tip_type=TipType.PINE_SHORT,
        )
        client.get_live_data.return_value = LiveDataResponse(
            live_temp=298,
            setpoint_temp=300,
            dc_voltage=20.6,
            handle_temp=36.3,
            pwm_level=41,
            power_src=PowerSource.PD,
            tip_resistance=6.2,
            uptime=1671,
            movement_time=10000,
            max_tip_temp_ability=460,
            tip_voltage=2212,
            hall_sensor=0,
            operating_mode=OperatingMode.SOLDERING,
            estimated_power=24.8,
        )
        yield client
