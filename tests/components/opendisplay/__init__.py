"""Tests for the OpenDisplay integration."""

from time import time

from bleak.backends.scanner import AdvertisementData
from opendisplay import (
    BinaryInputs,
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
ENCRYPTION_KEY = "aabbccddee112233aabbccddee112233"  # 32 hex chars = 16 bytes

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


BINARY_INPUT = BinaryInputs(
    instance_number=0,
    input_type=0,
    display_as=0,
    reserved_pins=b"\x00" * 8,
    input_flags=0x01,  # bit 0 set → button_id 0 active
    invert=0,
    pullups=0,
    pulldowns=0,
    button_data_byte_index=0,
)

BUTTON_DEVICE_CONFIG = GlobalConfig(
    system=DEVICE_CONFIG.system,
    manufacturer=DEVICE_CONFIG.manufacturer,
    power=DEVICE_CONFIG.power,
    displays=DEVICE_CONFIG.displays,
    binary_inputs=[BINARY_INPUT],
)


def make_v1_service_info(
    dynamic_data: bytes = b"\x00" * 11,
    name: str | None = "OpenDisplay 1234",
    address: str = TEST_ADDRESS,
) -> BluetoothServiceInfoBleak:
    """Create a v1 advertisement service info with a custom 11-byte dynamic block."""
    # temperature=25.0°C, battery≈3700 mV, loop_counter=1
    return make_service_info(
        name=name,
        address=address,
        manufacturer_data={OPENDISPLAY_MANUFACTURER_ID: dynamic_data + b"\x82\x72\x11"},
    )


def make_binary_inputs(
    instance_number: int = 0,
    byte_index: int = 0,
    input_flags: int = 0x01,
) -> BinaryInputs:
    """Create a minimal BinaryInputs config entry.

    input_flags is a bitmask of active inputs: bit N set means button_id N is active.
    """
    return BinaryInputs(
        instance_number=instance_number,
        input_type=0,
        display_as=0,
        reserved_pins=b"\x00" * 8,
        input_flags=input_flags,
        invert=0,
        pullups=0,
        pulldowns=0,
        button_data_byte_index=byte_index,
    )


def make_button_device_config(binary_inputs: list[BinaryInputs]) -> GlobalConfig:
    """Return a GlobalConfig with the given binary_inputs list."""
    return GlobalConfig(
        system=DEVICE_CONFIG.system,
        manufacturer=DEVICE_CONFIG.manufacturer,
        power=DEVICE_CONFIG.power,
        displays=DEVICE_CONFIG.displays,
        binary_inputs=binary_inputs,
    )


VALID_SERVICE_INFO = make_service_info()

NOT_OPENDISPLAY_SERVICE_INFO = make_service_info(
    name="Other Device",
    manufacturer_data={0x1234: b"\x00\x01"},
)
