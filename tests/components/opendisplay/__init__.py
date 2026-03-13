"""Tests for the OpenDisplay integration."""

from time import time

from bleak.backends.scanner import AdvertisementData
from opendisplay import (
    BoardManufacturer,
    ColorScheme,
    DisplayConfig,
    GlobalConfig,
    ManufacturerData,
    PowerOption,
    SystemConfig,
)

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_ble_device

OPENDISPLAY_MANUFACTURER_ID = 9286  # 0x2446

# V1 advertisement payload (14 bytes): battery_mv=3700, temperature_c=25.0, loop_counter=1
V1_ADVERTISEMENT_DATA = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x82\x72\x11"

TEST_ADDRESS = "AA:BB:CC:DD:EE:FF"
TEST_TITLE = "OpenDisplay 1234"

# Firmware version response: major=1, minor=2, sha="abc123"
FIRMWARE_VERSION = {"major": 1, "minor": 2, "sha": "abc123"}

DEVICE_CONFIG = GlobalConfig(
    system=SystemConfig(
        ic_type=0,
        communication_modes=0,
        device_flags=0,
        pwr_pin=0xFF,
        reserved=b"\x00" * 17,
    ),
    manufacturer=ManufacturerData(
        manufacturer_id=BoardManufacturer.SEEED,
        board_type=1,
        board_revision=0,
        reserved=b"\x00" * 18,
    ),
    power=PowerOption(
        power_mode=0,
        battery_capacity_mah=b"\x00" * 3,
        sleep_timeout_ms=0,
        tx_power=0,
        sleep_flags=0,
        battery_sense_pin=0xFF,
        battery_sense_enable_pin=0xFF,
        battery_sense_flags=0,
        capacity_estimator=0,
        voltage_scaling_factor=0,
        deep_sleep_current_ua=0,
        deep_sleep_time_seconds=0,
        reserved=b"\x00" * 12,
    ),
    displays=[
        DisplayConfig(
            instance_number=0,
            display_technology=0,
            panel_ic_type=0,
            pixel_width=296,
            pixel_height=128,
            active_width_mm=67,
            active_height_mm=29,
            tag_type=0,
            rotation=0,
            reset_pin=0xFF,
            busy_pin=0xFF,
            dc_pin=0xFF,
            cs_pin=0xFF,
            data_pin=0,
            partial_update_support=0,
            color_scheme=ColorScheme.BWR.value,
            transmission_modes=0x01,
            clk_pin=0,
            reserved_pins=b"\x00" * 7,
            full_update_mC=0,
            reserved=b"\x00" * 33,
        )
    ],
)


def make_service_info(
    name: str | None = "OpenDisplay 1234",
    address: str = "AA:BB:CC:DD:EE:FF",
    manufacturer_data: dict[int, bytes] | None = None,
) -> BluetoothServiceInfoBleak:
    """Create a BluetoothServiceInfoBleak for testing."""
    if manufacturer_data is None:
        manufacturer_data = {OPENDISPLAY_MANUFACTURER_ID: V1_ADVERTISEMENT_DATA}
    return BluetoothServiceInfoBleak(
        name=name or "",
        address=address,
        rssi=-60,
        manufacturer_data=manufacturer_data,
        service_data={},
        service_uuids=[],
        source="local",
        connectable=True,
        time=time(),
        device=generate_ble_device(address, name=name),
        advertisement=AdvertisementData(
            local_name=name,
            manufacturer_data=manufacturer_data,
            service_data={},
            service_uuids=[],
            rssi=-60,
            tx_power=-127,
            platform_data=(),
        ),
        tx_power=-127,
    )


VALID_SERVICE_INFO = make_service_info()

NOT_OPENDISPLAY_SERVICE_INFO = make_service_info(
    name="Other Device",
    manufacturer_data={0x1234: b"\x00\x01"},
)
