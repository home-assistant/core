"""Test scheduling and Home Assistant interpretation of BM2 readings."""

from unittest.mock import AsyncMock, MagicMock, patch

from bleak import BLEDevice
from bmx_ble import BM2Generation, BM2Protocol, BM2Reading
from bmx_ble.battery import BATTERY_PROFILES, Battery, BatteryReading
import pytest
from sensor_state_data import SensorUpdate

from homeassistant.components.bmx_monitor.const import (
    CONF_BATTERY_TYPE,
    CONF_CUSTOM_BATTERY_CHEMISTRY,
    CONF_CUSTOM_CHARGING_VOLTAGE,
    CONF_CUSTOM_CRITICAL_VOLTAGE,
    CONF_CUSTOM_FLOATING_VOLTAGE,
    CONF_CUSTOM_LOW_VOLTAGE,
    CONF_CUSTOM_NUMPY_VOLTS,
    CONF_RATE_LIMIT,
    CONF_RATE_LIMIT_MODE,
    DOMAIN,
)
from homeassistant.components.bmx_monitor.device_data import BMxBluetoothDeviceData

from tests.common import MockConfigEntry

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.fixture
def device() -> BMxBluetoothDeviceData:
    """Create real HA data handling with independent options."""
    data = BMxBluetoothDeviceData()
    data.entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS)
    return data


def test_advertisement_metadata(device: BMxBluetoothDeviceData) -> None:
    """Refresh metadata and delegate the packet to the protocol library."""
    info = MagicMock()
    info.address = ADDRESS
    info.manufacturer_data = {76: b"test"}
    with (
        patch.object(device, "set_device_manufacturer") as manufacturer,
        patch.object(device, "set_device_type") as model,
        patch.object(device, "set_device_name") as name,
        patch.object(device, "set_title") as title,
        patch.object(device, "process_advertisement") as decode,
    ):
        device._start_update(info)
    manufacturer.assert_called_once_with("Shenzhen Leagend Optoelectronics")
    model.assert_called_once_with("BM2 battery monitor")
    name.assert_called_once()
    assert name.call_args == title.call_args
    assert "BM2 battery monitor" in name.call_args.args[0]
    decode.assert_called_once_with(info.manufacturer_data)


@pytest.mark.parametrize(
    ("ignored", "last_poll", "mode", "charging", "expected"),
    [
        (True, None, "never", False, False),
        (False, None, "always", False, True),
        (False, 0.0, "never", False, True),
        (False, 0.0, "when_not_charging", True, True),
        (False, 0.0, "when_charging", False, True),
        (False, 10.0, "always", False, False),
        (False, 11.0, "always", False, True),
        (False, 10.0, "when_not_charging", False, False),
        (False, 11.0, "when_charging", True, True),
    ],
)
def test_poll_schedule(
    device: BMxBluetoothDeviceData,
    ignored: bool,
    last_poll: float | None,
    mode: str,
    charging: bool,
    expected: bool,
) -> None:
    """Respect in-progress reads, first polls, charging modes and limits."""
    device.entry = MockConfigEntry(
        domain=DOMAIN, options={CONF_RATE_LIMIT_MODE: mode, CONF_RATE_LIMIT: 10}
    )
    device._ignore_advertisement = ignored
    device._charging = charging
    assert device.poll_needed(MagicMock(address=ADDRESS), last_poll) is expected


@pytest.mark.parametrize(
    ("option", "battery"),
    [
        ("Automatic (via BM2)", Battery.automatic),
        ("AGM", Battery.agm),
        ("Deep-cycle", Battery.deepcycle),
        ("Lead-acid", Battery.leadacid),
        ("LiFePO4", Battery.lifepo4),
        ("LifePO4", Battery.lifepo4),
        ("Lithium-ion", Battery.lithiumion),
        ("iTechworld 120X (LiFePO4)", Battery.itech120x),
        ("itech120x", Battery.itech120x),
    ],
)
def test_chemistry_selection(
    device: BMxBluetoothDeviceData, option: str, battery: Battery
) -> None:
    """Known options select the intended chemistry."""
    device.entry = MockConfigEntry(domain=DOMAIN, options={CONF_BATTERY_TYPE: option})
    assert device._battery_profile() is BATTERY_PROFILES[battery]


def test_custom_chemistry_is_independent(device: BMxBluetoothDeviceData) -> None:
    """A custom curve never mutates shared predefined battery details."""
    device.entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_BATTERY_TYPE: "Custom",
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
    ("status", "expected", "charging"),
    [(4, "charging", True), (2, "normal", False), (99, "unknown", False)],
)
def test_automatic_reading(
    device: BMxBluetoothDeviceData, status: int, expected: str, charging: bool
) -> None:
    """Automatic mode publishes monitor values and known generation."""
    device._bm2_generation = BM2Generation.ENHANCED
    with patch.object(device, "update_sensor") as publish:
        device._apply_reading(BM2Reading(12.5, 67, status, "active"))
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
    assert device._charging is charging


def test_partial_reading_preserves_unavailable_fields(
    device: BMxBluetoothDeviceData,
) -> None:
    """Legacy percentage-only packets do not overwrite voltage or status."""
    with patch.object(device, "update_sensor") as publish:
        device._apply_reading(BM2Reading(None, 45, None, "advertisement"))
    values = {
        call.kwargs["key"]: call.kwargs["native_value"]
        for call in publish.call_args_list
    }
    assert values == {"battery_chemistry": "Automatic", "battery_percent": 45}


def test_chemistry_adjusts_reading(device: BMxBluetoothDeviceData) -> None:
    """Configured chemistry replaces the raw percentage and missing status."""
    device.entry = MockConfigEntry(
        domain=DOMAIN, options={CONF_BATTERY_TYPE: "Lead-acid"}
    )
    with patch.object(device, "update_sensor") as publish:
        device._apply_reading(BM2Reading(12.06, 99, None, "advertisement"))
    values = {
        call.kwargs["key"]: call.kwargs["native_value"]
        for call in publish.call_args_list
    }
    assert values["battery_percent"] == 50
    assert values["battery_status"] == "critical"
    assert values["battery_chemistry"] == "Lead-acid"


@pytest.mark.parametrize("ble_device", [None, BLEDevice(ADDRESS, "BM2", {})])
async def test_poll_publishes_protocol_reading(
    device: BMxBluetoothDeviceData, ble_device: BLEDevice | None
) -> None:
    """Publish the library reading for active and passive-only paths."""
    reading = BM2Reading(12.5, 60, 2, "active")
    with patch.object(
        BM2Protocol, "async_poll", new_callable=AsyncMock, return_value=reading
    ) as poll:
        update = await device.async_poll_sensors(ble_device)
    poll.assert_awaited_once_with(device, ble_device)
    assert isinstance(update, SensorUpdate)
    values = {
        key.key: value.native_value for key, value in update.entity_values.items()
    }
    assert values["battery_voltage"] == 12.5
    assert values["battery_percent"] == 60


def test_custom_profile_defaults(device: BMxBluetoothDeviceData) -> None:
    """An entry without explicit custom thresholds uses the form defaults."""
    device.entry = MockConfigEntry(domain=DOMAIN, options={CONF_BATTERY_TYPE: "Custom"})
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
        device._apply_reading(raw)
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
    assert device._charging is True


def test_missing_status_preserves_charging(device: BMxBluetoothDeviceData) -> None:
    """A partial fallback must not reset the last known charging state."""
    device._charging = True
    device._apply_reading(BM2Reading(None, 45, None, "advertisement"))
    assert device._charging is True
