"""Test scheduling and Home Assistant interpretation of BM2 readings."""

from unittest.mock import AsyncMock, MagicMock, patch

from bleak import BLEDevice
from bleak.exc import BleakError
from bmx_ble import BM2Generation, BM2Protocol, BM2Reading
from bmx_ble.battery import BATTERY_PROFILES, Battery, BatteryReading
import pytest
from pytest_homeassistant.common import MockConfigEntry
from sensor_state_data import SensorUpdate

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bmx_monitor.const import (
    CONF_BATTERY_TYPE,
    CONF_CUSTOM_BATTERY_CHEMISTRY,
    CONF_CUSTOM_CHARGING_VOLTAGE,
    CONF_CUSTOM_CRITICAL_VOLTAGE,
    CONF_CUSTOM_FLOATING_VOLTAGE,
    CONF_CUSTOM_LOW_VOLTAGE,
    CONF_CUSTOM_NUMPY_VOLTS,
    DOMAIN,
)
from homeassistant.components.bmx_monitor.device_data import (
    MIN_POLL_INTERVAL,
    BMxBluetoothDeviceData,
)

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.fixture
def device() -> BMxBluetoothDeviceData:
    """Create real HA data handling with independent options."""
    data = BMxBluetoothDeviceData()
    data.entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS)
    return data


def test_advertisement_metadata(device: BMxBluetoothDeviceData) -> None:
    """Refresh metadata and delegate the packet to the protocol library."""
    info = MagicMock(spec=BluetoothServiceInfoBleak)
    info.address = ADDRESS
    info.manufacturer_data = {76: b"test"}
    with (
        patch.object(device, "set_device_manufacturer") as manufacturer,
        patch.object(device, "set_device_type") as model,
        patch.object(device, "set_device_name") as name,
        patch.object(device, "set_title") as title,
        patch.object(device, "process_advertisement", return_value=None) as decode,
        patch.object(device, "update_sensor") as publish,
    ):
        device._start_update(info)
    manufacturer.assert_called_once_with("Shenzhen Leagend Optoelectronics")
    model.assert_called_once_with("BM2 battery monitor")
    name.assert_called_once()
    assert name.call_args == title.call_args
    assert "BM2 battery monitor" in name.call_args.args[0]
    decode.assert_called_once_with(info.manufacturer_data, raw=info.raw)
    publish.assert_not_called()


@pytest.mark.parametrize(
    ("generation", "battery", "last_poll", "expected"),
    [
        pytest.param(
            BM2Generation.UNKNOWN, Battery.leadacid, None, True, id="unknown-first"
        ),
        pytest.param(
            BM2Generation.LEGACY, Battery.automatic, None, True, id="legacy-auto-first"
        ),
        pytest.param(
            BM2Generation.LEGACY,
            Battery.leadacid,
            MIN_POLL_INTERVAL - 0.1,
            False,
            id="legacy-chosen-too-soon",
        ),
        pytest.param(
            BM2Generation.LEGACY,
            Battery.leadacid,
            MIN_POLL_INTERVAL,
            True,
            id="legacy-chosen-due",
        ),
        pytest.param(
            BM2Generation.ENHANCED,
            Battery.automatic,
            MIN_POLL_INTERVAL,
            True,
            id="enhanced-auto-due",
        ),
        pytest.param(
            BM2Generation.ENHANCED,
            Battery.leadacid,
            None,
            False,
            id="enhanced-chosen-never",
        ),
        pytest.param(
            BM2Generation.ENHANCED,
            Battery.custom,
            None,
            False,
            id="enhanced-custom-never",
        ),
    ],
)
def test_poll_schedule(
    device: BMxBluetoothDeviceData,
    generation: BM2Generation,
    battery: Battery,
    last_poll: float | None,
    expected: bool,
) -> None:
    """Connect only for data the advertisement lacks, at a fixed interval."""
    device.entry = MockConfigEntry(
        domain=DOMAIN, options={CONF_BATTERY_TYPE: battery.value}
    )
    device._bm2_generation = generation
    assert device.poll_needed(MagicMock(address=ADDRESS), last_poll) is expected


def test_no_poll_while_reading(device: BMxBluetoothDeviceData) -> None:
    """An advertisement during a read must not queue a second connection."""
    device._ignore_advertisement = True
    assert not device.poll_needed(MagicMock(address=ADDRESS), None)


@pytest.mark.parametrize(
    "battery", [battery for battery in Battery if battery is not Battery.custom]
)
def test_chemistry_selection(device: BMxBluetoothDeviceData, battery: Battery) -> None:
    """Stored identifiers select profiles without relying on display labels."""
    device.entry = MockConfigEntry(
        domain=DOMAIN, options={CONF_BATTERY_TYPE: battery.value}
    )
    assert device._battery_profile() is BATTERY_PROFILES[battery]


def test_custom_chemistry_is_independent(device: BMxBluetoothDeviceData) -> None:
    """A custom curve never mutates shared predefined battery details."""
    device.entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_BATTERY_TYPE: Battery.custom.value,
            CONF_CUSTOM_BATTERY_CHEMISTRY: "Test chemistry",
            CONF_CUSTOM_NUMPY_VOLTS: [11.0, 11.5, 12.3, 12.8],
            CONF_CUSTOM_CRITICAL_VOLTAGE: 11.0,
            CONF_CUSTOM_LOW_VOLTAGE: 11.5,
            CONF_CUSTOM_FLOATING_VOLTAGE: 13.5,
            CONF_CUSTOM_CHARGING_VOLTAGE: 14.4,
        },
    )
    detail = device._battery_profile()
    assert detail.battery_chemistry == "Test chemistry"
    assert detail.volts_to_percent == (11.0, 11.5, 12.3, 12.8)
    assert detail.percentages == (0, 20, 50, 100)
    assert detail.floating_voltage == 13.5
    assert detail.charging_voltage == 14.4
    assert device._battery_profile() is not detail


@pytest.mark.parametrize(
    ("status", "expected"),
    [(4, "charging"), (2, "normal"), (99, None)],
)
def test_automatic_reading(
    device: BMxBluetoothDeviceData, status: int, expected: str | None
) -> None:
    """Automatic mode publishes monitor values and known generation."""
    device._bm2_generation = BM2Generation.ENHANCED
    with patch.object(device, "update_sensor") as publish:
        device._apply_reading(
            BM2Reading(12.5, 67, status, "active"), device._battery_profile()
        )
    values = {
        call.kwargs["key"]: call.kwargs["native_value"]
        for call in publish.call_args_list
    }
    assert values == {
        "battery_chemistry": "Automatic",
        "battery_percent": 67,
        "battery_voltage": 12.5,
        "battery_status": expected,
        "bm2_generation": str(BM2Generation.ENHANCED),
    }


def test_partial_reading_preserves_unavailable_fields(
    device: BMxBluetoothDeviceData,
) -> None:
    """Legacy percentage-only packets do not overwrite voltage or status."""
    with patch.object(device, "update_sensor") as publish:
        device._apply_reading(
            BM2Reading(None, 45, None, "advertisement"), device._battery_profile()
        )
    values = {
        call.kwargs["key"]: call.kwargs["native_value"]
        for call in publish.call_args_list
    }
    assert values == {"battery_chemistry": "Automatic", "battery_percent": 45}


def test_chemistry_adjusts_reading(device: BMxBluetoothDeviceData) -> None:
    """Configured chemistry replaces the raw percentage and missing status."""
    device.entry = MockConfigEntry(
        domain=DOMAIN, options={CONF_BATTERY_TYPE: Battery.leadacid.value}
    )
    with patch.object(device, "update_sensor") as publish:
        device._apply_reading(
            BM2Reading(12.06, 99, None, "advertisement"), device._battery_profile()
        )
    values = {
        call.kwargs["key"]: call.kwargs["native_value"]
        for call in publish.call_args_list
    }
    assert values["battery_percent"] == 50
    assert values["battery_status"] == "critical"
    assert values["battery_chemistry"] == "Lead-acid"


async def test_poll_publishes_protocol_reading(
    device: BMxBluetoothDeviceData,
) -> None:
    """Publish the library's GATT reading."""
    ble_device = BLEDevice(ADDRESS, "BM2", {})
    reading = BM2Reading(12.5, 60, 2, "active")
    with patch.object(
        BM2Protocol, "async_poll", new_callable=AsyncMock, return_value=reading
    ) as poll:
        update = await device.async_poll_sensors(ble_device)
    poll.assert_awaited_once_with(ble_device)
    assert isinstance(update, SensorUpdate)
    values = {
        key.key: value.native_value for key, value in update.entity_values.items()
    }
    assert values["battery_voltage"] == 12.5
    assert values["battery_percent"] == 60


def test_custom_profile_defaults(device: BMxBluetoothDeviceData) -> None:
    """An entry without explicit custom thresholds uses the form defaults."""
    device.entry = MockConfigEntry(
        domain=DOMAIN, options={CONF_BATTERY_TYPE: Battery.custom.value}
    )
    profile = device._battery_profile()
    assert profile.battery_chemistry == "Custom battery"
    assert profile.volts_to_percent == (12.06, 12.2, 12.3, 12.7)
    assert profile.floating_voltage == 13.7
    assert profile.charging_voltage == 14.5


def test_reading_interpretation_is_delegated(device: BMxBluetoothDeviceData) -> None:
    """The adapter publishes library results instead of calculating them."""
    raw = BM2Reading(12.5, 67, 2, "active")
    interpreted = BatteryReading("Library chemistry", 12.8, 80, "floating", True)
    with (
        patch(
            "homeassistant.components.bmx_monitor.device_data.interpret_reading",
            return_value=interpreted,
        ) as interpret,
        patch.object(device, "update_sensor") as publish,
    ):
        device._apply_reading(raw, BATTERY_PROFILES[Battery.automatic])
    interpret.assert_called_once_with(raw, BATTERY_PROFILES[Battery.automatic])
    values = {
        call.kwargs["key"]: call.kwargs["native_value"]
        for call in publish.call_args_list
    }
    assert values == {
        "battery_chemistry": "Library chemistry",
        "battery_voltage": 12.8,
        "battery_percent": 80,
        "battery_status": "floating",
    }


async def test_failed_poll_raises(device: BMxBluetoothDeviceData) -> None:
    """A failed read propagates and publishes nothing."""
    with (
        patch.object(
            BM2Protocol,
            "async_poll",
            new_callable=AsyncMock,
            side_effect=BleakError("connection failed"),
        ),
        patch.object(device, "update_sensor") as publish,
        pytest.raises(BleakError, match="connection failed"),
    ):
        await device.async_poll_sensors(BLEDevice(ADDRESS, "BM2", {}))
    publish.assert_not_called()
