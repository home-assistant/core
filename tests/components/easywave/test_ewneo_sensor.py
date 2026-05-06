"""Tests for EWneo temperature and humidity sensor entities."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.easywave.const import (
    CONF_ENTRY_TYPE,
    CONF_SENSOR_SERIAL,
    CONF_SENSOR_TYPES,
    DOMAIN,
    ENTRY_TYPE_SENSOR,
    NEO_SENSOR_TYPE_HUMIDITY,
    NEO_SENSOR_TYPE_TEMPERATURE,
    SENSOR_KIND_HUMIDITY,
    SENSOR_KIND_TEMPERATURE,
)
from homeassistant.components.easywave.entity import EasywaveDeviceEntry
from homeassistant.components.easywave.sensor import (
    EWneoHumiditySensor,
    EWneoTemperatureSensor,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant

from .conftest import MOCK_ENTRY_DATA

from tests.common import MockConfigEntry

MOCK_SENSOR_SERIAL = "deadbeef" + "00" * 12
MOCK_SUBENTRY_ID = "sensor_subentry_test"


def _make_sensor_subentry(
    sensor_types: list[str],
    subentry_id: str = MOCK_SUBENTRY_ID,
) -> EasywaveDeviceEntry:
    """Return an EasywaveDeviceEntry with sensor data."""
    return EasywaveDeviceEntry(
        subentry_id=subentry_id,
        title="Test Sensor",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_SENSOR,
            CONF_SENSOR_SERIAL: MOCK_SENSOR_SERIAL,
            CONF_SENSOR_TYPES: sensor_types,
        },
    )


def _make_gateway_entry(
    sensor_types: list[str] | None = None,
) -> MockConfigEntry:
    """Return a gateway entry, optionally with a sensor device in options."""
    devices: list[dict] = []
    if sensor_types is not None:
        devices.append(
            {
                "id": MOCK_SUBENTRY_ID,
                "title": "Test Sensor",
                "unique_id": f"sensor_{MOCK_SENSOR_SERIAL}",
                "data": {
                    CONF_ENTRY_TYPE: ENTRY_TYPE_SENSOR,
                    CONF_SENSOR_SERIAL: MOCK_SENSOR_SERIAL,
                    CONF_SENSOR_TYPES: sensor_types,
                },
            }
        )
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options={"devices": devices},
    )


def _make_runtime_data() -> MagicMock:
    """Return mock runtime_data with a coordinator."""
    mock_transceiver = MagicMock()
    mock_transceiver.is_connected = True
    mock_coordinator = MagicMock()
    mock_coordinator.transceiver = mock_transceiver
    mock_coordinator.register_sensor_entities = MagicMock()
    mock_coordinator.unregister_sensor_entity = MagicMock()
    runtime_data = MagicMock()
    runtime_data.coordinator = mock_coordinator
    return runtime_data


# ── async_setup_entry: correct entity count ───────────────────────────────────


@pytest.mark.parametrize(
    ("sensor_types", "expected_sensor_count"),
    [
        ([SENSOR_KIND_TEMPERATURE], 1),
        ([SENSOR_KIND_HUMIDITY], 1),
        ([SENSOR_KIND_TEMPERATURE, SENSOR_KIND_HUMIDITY], 2),
        ([], 0),
    ],
)
async def test_sensor_setup_creates_correct_entities(
    hass: HomeAssistant,
    sensor_types: list[str],
    expected_sensor_count: int,
) -> None:
    """Test async_setup_entry creates the right number of sensor entities."""
    entry = _make_gateway_entry(sensor_types)
    entry.runtime_data = _make_runtime_data()
    added: list = []

    await async_setup_entry(
        hass, entry, lambda entities, *args, **kwargs: added.extend(entities)
    )

    # 1 gateway status sensor + expected per-subentry sensor count + 1 battery sensor
    assert len(added) == 2 + expected_sensor_count
    if SENSOR_KIND_TEMPERATURE in sensor_types:
        assert any(isinstance(e, EWneoTemperatureSensor) for e in added)
    if SENSOR_KIND_HUMIDITY in sensor_types:
        assert any(isinstance(e, EWneoHumiditySensor) for e in added)


# ── Temperature sensor value parsing ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected_celsius"),
    [
        (5863, 20.0),  # (5863/20) - 273.15 = 293.15 - 273.15 = 20.0 °C
        (5463, 0.0),  # (5463/20) - 273.15 = 273.15 - 273.15 = 0.0 °C
        (4643, -41.0),  # (4643/20) - 273.15 = 232.15 - 273.15 = -41.0 °C
        (6063, 30.0),  # (6063/20) - 273.15 = 303.15 - 273.15 = 30.0 °C
    ],
)
def test_temperature_parse_value(raw: int, expected_celsius: float) -> None:
    """Test EWneoTemperatureSensor._parse_value() returns correct °C."""
    entry = _make_gateway_entry()
    subentry = _make_sensor_subentry([SENSOR_KIND_TEMPERATURE])
    entry.runtime_data = _make_runtime_data()
    sensor = EWneoTemperatureSensor(entry, subentry)

    result = sensor._parse_value(NEO_SENSOR_TYPE_TEMPERATURE, raw)
    assert result == expected_celsius


def test_temperature_parse_wrong_type_returns_none() -> None:
    """Test that a wrong sensor_type_code returns None for temperature sensor."""
    entry = _make_gateway_entry()
    subentry = _make_sensor_subentry([SENSOR_KIND_TEMPERATURE])
    entry.runtime_data = _make_runtime_data()
    sensor = EWneoTemperatureSensor(entry, subentry)

    assert sensor._parse_value(NEO_SENSOR_TYPE_HUMIDITY, 5863) is None
    assert sensor._parse_value(0, 5863) is None


# ── Humidity sensor value parsing ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected_pct"),
    [
        (1638, 40.0),  # 1638/4095*100 = 40.0%
        (0, 0.0),  # 0/4095*100 = 0.0%
        (4095, 100.0),  # 4095/4095*100 = 100.0%
        (2048, 50.0),  # 2048/4095*100 ≈ 50.0%
    ],
)
def test_humidity_parse_value(raw: int, expected_pct: float) -> None:
    """Test EWneoHumiditySensor._parse_value() returns correct %."""
    entry = _make_gateway_entry()
    subentry = _make_sensor_subentry([SENSOR_KIND_HUMIDITY])
    entry.runtime_data = _make_runtime_data()
    sensor = EWneoHumiditySensor(entry, subentry)

    result = sensor._parse_value(NEO_SENSOR_TYPE_HUMIDITY, raw)
    assert result == expected_pct


def test_humidity_parse_wrong_type_returns_none() -> None:
    """Test that a wrong sensor_type_code returns None for humidity sensor."""
    entry = _make_gateway_entry()
    subentry = _make_sensor_subentry([SENSOR_KIND_HUMIDITY])
    entry.runtime_data = _make_runtime_data()
    sensor = EWneoHumiditySensor(entry, subentry)

    assert sensor._parse_value(NEO_SENSOR_TYPE_TEMPERATURE, 2000) is None


# ── handle_telegram behaviour ─────────────────────────────────────────────────


def _build_data_telegram(sensor_type_code: int, raw: int) -> bytes:
    """Build an 8-byte EWneo sensor data telegram (not a learn telegram)."""
    high = (raw >> 8) & 0xFF
    low = raw & 0xFF
    return bytes([0x00, 0x00, sensor_type_code << 2, high, low, 0x00, 0x00, 0x00])


def test_temperature_handle_telegram_updates_value() -> None:
    """handle_telegram with 20°C raw data should set native_value to 20.0."""
    entry = _make_gateway_entry()
    subentry = _make_sensor_subentry([SENSOR_KIND_TEMPERATURE])
    entry.runtime_data = _make_runtime_data()
    sensor = EWneoTemperatureSensor(entry, subentry)
    sensor.async_write_ha_state = MagicMock()

    # 20.0 °C → raw = 5863
    sensor.handle_telegram(_build_data_telegram(NEO_SENSOR_TYPE_TEMPERATURE, 5863))
    assert sensor.native_value == 20.0


def test_temperature_handle_telegram_ignores_wrong_type() -> None:
    """handle_telegram with humidity type code should not update temperature sensor."""
    entry = _make_gateway_entry()
    subentry = _make_sensor_subentry([SENSOR_KIND_TEMPERATURE])
    entry.runtime_data = _make_runtime_data()
    sensor = EWneoTemperatureSensor(entry, subentry)
    sensor.async_write_ha_state = MagicMock()

    sensor.handle_telegram(_build_data_telegram(NEO_SENSOR_TYPE_HUMIDITY, 2048))
    assert sensor.native_value is None  # not updated


def test_handle_telegram_skips_learn_flag() -> None:
    """handle_telegram should skip telegrams with the learn flag (byte1 bit7=1)."""
    entry = _make_gateway_entry()
    subentry = _make_sensor_subentry([SENSOR_KIND_TEMPERATURE])
    entry.runtime_data = _make_runtime_data()
    sensor = EWneoTemperatureSensor(entry, subentry)
    sensor.async_write_ha_state = MagicMock()

    # Byte 1 has bit7=1 (learn flag)
    learn_data = bytes(
        [0x00, 0x80, NEO_SENSOR_TYPE_TEMPERATURE << 2, 0x16, 0xE7, 0, 0, 0]
    )
    sensor.handle_telegram(learn_data)
    assert sensor.native_value is None  # skipped


def test_handle_telegram_too_short_ignored() -> None:
    """handle_telegram with < 5 bytes should be silently ignored."""
    entry = _make_gateway_entry()
    subentry = _make_sensor_subentry([SENSOR_KIND_TEMPERATURE])
    entry.runtime_data = _make_runtime_data()
    sensor = EWneoTemperatureSensor(entry, subentry)
    sensor.async_write_ha_state = MagicMock()

    sensor.handle_telegram(b"\x00\x00")
    assert sensor.native_value is None


def test_humidity_handle_telegram_updates_value() -> None:
    """handle_telegram with 40% raw data should set native_value to 40.0."""
    entry = _make_gateway_entry()
    subentry = _make_sensor_subentry([SENSOR_KIND_HUMIDITY])
    entry.runtime_data = _make_runtime_data()
    sensor = EWneoHumiditySensor(entry, subentry)
    sensor.async_write_ha_state = MagicMock()

    # 40% → raw = 1638
    sensor.handle_telegram(_build_data_telegram(NEO_SENSOR_TYPE_HUMIDITY, 1638))
    assert sensor.native_value == 40.0


# ── Entity attributes ─────────────────────────────────────────────────────────


def test_temperature_unique_id() -> None:
    """Temperature sensor unique_id includes device_id and 'temperature' suffix."""
    entry = _make_gateway_entry()
    subentry = _make_sensor_subentry([SENSOR_KIND_TEMPERATURE])
    entry.runtime_data = _make_runtime_data()
    sensor = EWneoTemperatureSensor(entry, subentry)
    assert sensor._attr_unique_id.endswith("_temperature")


def test_humidity_unique_id() -> None:
    """Humidity sensor unique_id includes device_id and 'humidity' suffix."""
    entry = _make_gateway_entry()
    subentry = _make_sensor_subentry([SENSOR_KIND_HUMIDITY])
    entry.runtime_data = _make_runtime_data()
    sensor = EWneoHumiditySensor(entry, subentry)
    assert sensor._attr_unique_id.endswith("_humidity")


def test_sensor_available_reflects_transceiver() -> None:
    """Sensor availability mirrors transceiver.is_connected."""
    entry = _make_gateway_entry()
    subentry = _make_sensor_subentry([SENSOR_KIND_TEMPERATURE])
    rt = _make_runtime_data()
    entry.runtime_data = rt
    sensor = EWneoTemperatureSensor(entry, subentry)

    rt.coordinator.transceiver.is_connected = True
    assert sensor.available is True

    rt.coordinator.transceiver.is_connected = False
    assert sensor.available is False
