"""Tests for live neo sensor entity updates from telegrams."""

from unittest.mock import MagicMock

from easywave_home_control.codec import MeasurementType, SensorTelegramEvent
from easywave_home_control.codec.common import TimerDuration
from easywave_home_control.codec.sensors import (
    SensorMeasurementPayload,
    SensorPayloadFormat,
)

from homeassistant.components.easywave.const import (
    CONF_ENTRY_TYPE,
    CONF_SENSOR_CAPABILITIES,
    CONF_SENSOR_SERIAL,
    ENTRY_TYPE_NEO_SENSOR,
)
from homeassistant.components.easywave.entity import EasywaveDeviceEntry
from homeassistant.components.easywave.sensor import EasywaveNeoSensorTemperatureSensor
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_SENSOR_SERIAL = "bb" * 16
NEO_SENSOR_CAPABILITIES = (1 << 4) | (1 << 5)


def _temperature_event() -> SensorTelegramEvent:
    """Return a temperature measurement telegram."""
    return SensorTelegramEvent(
        sensor_serial=bytes.fromhex(MOCK_SENSOR_SERIAL),
        payload=SensorMeasurementPayload(
            version=0,
            has_battery=True,
            battery_level=7,
            wire_measurement_type=5,
            measurement_type=MeasurementType.TEMPERATURE,
            payload_format=SensorPayloadFormat.NEO,
            should_ignore=False,
            has_reference=False,
            raw_value=2630,
            reference_value=0,
            max_interval=TimerDuration(mantissa=0, exponent=0, factor_minutes=15.0),
        ),
    )


async def test_neo_sensor_temperature_entity_updates_from_telegram(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
) -> None:
    """A matching measurement telegram updates the temperature entity state."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = MagicMock(coordinator=mock_coordinator)

    device = EasywaveDeviceEntry(
        device_id=f"neo_sensor_{MOCK_SENSOR_SERIAL}",
        title="Living Room Sensor",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_NEO_SENSOR,
            CONF_SENSOR_SERIAL: MOCK_SENSOR_SERIAL,
            CONF_SENSOR_CAPABILITIES: NEO_SENSOR_CAPABILITIES,
        },
    )
    entity = EasywaveNeoSensorTemperatureSensor(mock_config_entry, device)
    entity.hass = hass
    entity.entity_id = "sensor.living_room_sensor_temperature"
    entity.async_write_ha_state = MagicMock()

    entity.handle_telegram(_temperature_event())

    assert entity.native_value == 26.3
    entity.async_write_ha_state.assert_called_once()
