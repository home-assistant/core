"""Tests for TFA.me: test of sensor.py."""

from datetime import datetime, timedelta
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.a_tfa_me_1.const import (
    CONF_INTERVAL,
    CONF_MULTIPLE_ENTITIES,
    DEVICE_MAPPING,
    DOMAIN,
    ICON_MAPPING,
    ICON_MAPPING_WIND_DIR,
)
from homeassistant.components.a_tfa_me_1.coordinator import TFAmeDataCoordinator
from homeassistant.components.a_tfa_me_1.sensor import (
    SensorHistory,
    TFAmeSensorEntity,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


@pytest.fixture
def mock_coordinator():
    """Return a mock coordinator with fake data."""
    coordinator = AsyncMock()
    coordinator.host = "192.168.1.10"
    coordinator.multiple_entities = False
    coordinator.sensor_entity_list = []

    now = datetime.now().timestamp()

    # {'sensor_id': 'a6f169ad1', 'gateway_id': '99fffff9d', 'sensor_name': 'A6F169AD1', 'measurement': 'temperature', 'value': '24.6', 'unit': '°C', 'timestamp': '2025-09-01T08:09:00Z', 'ts': '1756714140', 'info': ''}
    coordinator.data = {
        "sensor.a01234567_temperature": {
            "sensor_id": "a01234567",
            "gateway_id": "017654321",
            "sensor_name": "A01234567",
            "measurement": "temperature",
            "value": "23.5",
            "unit": "°C",
            "timestamp": "2025-09-01T08:46:01Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a6f169ad1_rssi": {
            "sensor_id": "a6f169ad1",
            "gateway_id": "017654321",
            "sensor_name": "A6F169AD1",
            "measurement": "rssi",
            "value": "233",
            "unit": "/255",
            "timestamp": "2025-09-02T09:15:13Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a6f169ad1_lowbatt": {
            "sensor_id": "a6f169ad1",
            "gateway_id": "017654321",
            "sensor_name": "A6F169AD1",
            "measurement": "lowbatt",
            "value": "1",
            "unit": "",
            "timestamp": "2025-09-02T09:15:13Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a6f169ad1_lowbatt_txt": {
            "sensor_id": "a6f169ad1",
            "gateway_id": "017654321",
            "sensor_name": "A6F169AD1",
            "measurement": "lowbatt_text",
            "value": "1",
            "text": "Yes",
            "uint": "",
            "timestamp": "2025-09-02T09:15:13Z",
            "ts": int(now),
        },
        "sensor.a6f169ad1_temperature": {
            "sensor_id": "a6f169ad1",
            "gateway_id": "017654321",
            "sensor_name": "A6F169AD1",
            "measurement": "temperature",
            "value": "24.7",
            "unit": "°C",
            "timestamp": "2025-09-02T09:15:13Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a6f169ad1_humidity": {
            "sensor_id": "a6f169ad1",
            "gateway_id": "017654321",
            "sensor_name": "A6F169AD1",
            "measurement": "humidity",
            "value": "50",
            "unit": "%",
            "timestamp": "2025-09-02T09:15:13Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a364f3d67_rssi": {
            "sensor_id": "a364f3d67",
            "gateway_id": "017654321",
            "sensor_name": "A364F3D67",
            "measurement": "rssi",
            "value": "232",
            "unit": "/255",
            "timestamp": "2025-09-02T09:12:33Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a364f3d67_lowbatt": {
            "sensor_id": "a364f3d67",
            "gateway_id": "017654321",
            "sensor_name": "A364F3D67",
            "measurement": "lowbatt",
            "value": "0",
            "unit": "",
            "timestamp": "2025-09-02T09:12:33Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a364f3d67_lowbatt_txt": {
            "sensor_id": "a364f3d67",
            "gateway_id": "99fffff9d",
            "sensor_name": "A364F3D67",
            "measurement": "lowbatt_text",
            "value": "0",
            "text": "No",
            "uint": "",
            "timestamp": "2025-09-02T09:12:33Z",
            "ts": int(now),
        },
        "sensor.a364f3d67_temperature": {
            "sensor_id": "a364f3d67",
            "gateway_id": "017654321",
            "sensor_name": "A364F3D67",
            "measurement": "temperature",
            "value": "24.5",
            "unit": "°C",
            "timestamp": "2025-09-02T09:12:33Z",
            "ts": int(now),
            "info": "",
        },
        # 'sensor.a4481290f_rssi': {'sensor_id': 'a4481290f', 'gateway_id': '99fffff9d', 'sensor_name': 'A4481290F', 'measurement': 'rssi', 'value': '213', 'unit': '/255', 'timestamp': '2025-09-02T09:15:16Z', 'ts': '1756804516', 'info': ''}, 'sensor.a4481290f_lowbatt': {'sensor_id': 'a4481290f', 'gateway_id': '99fffff9d', 'sensor_name': 'A4481290F', 'measurement': 'lowbatt', 'value': '1', 'unit': '', 'timestamp': '2025-09-02T09:15:16Z', 'ts': '1756804516', 'info': ''}, 'sensor.a4481290f_lowbatt_txt': {'sensor_id': 'a4481290f', 'gateway_id': '99fffff9d', 'sensor_name': 'A4481290F', 'measurement': 'lowbatt_text', 'value': '1', 'text': 'Yes', 'uint': '', 'timestamp': '2025-09-02T09:15:16Z', 'ts': '1756804516'}, 'sensor.a4481290f_temperature': {'sensor_id': 'a4481290f', 'gateway_id': '99fffff9d', 'sensor_name': 'A4481290F', 'measurement': 'temperature', 'value': '24.2', 'unit': '°C', 'timestamp': '2025-09-02T09:15:16Z', 'ts': '1756804516', 'info': ''}, 'sensor.a4481290f_humidity': {'sensor_id': 'a4481290f', 'gateway_id': '99fffff9d', 'sensor_name': 'A4481290F', 'measurement': 'humidity', 'value': '52', 'unit': '%', 'timestamp': '2025-09-02T09:15:16Z', 'ts': '1756804516', 'info': ''}, 'sensor.a4481290f_temperature_probe': {'sensor_id': 'a4481290f', 'gateway_id': '99fffff9d', 'sensor_name': 'A4481290F', 'measurement': 'temperature_probe', 'value': '24.5', 'unit': '°C', 'timestamp': '2025-09-02T09:15:16Z', 'ts': '1756804516', 'info': ''}, 'sensor.a2ffffffb_rssi': {'sensor_id': 'a2ffffffb', 'gateway_id': '99fffff9d', 'sensor_name': 'A2FFFFFFB', 'measurement': 'rssi', 'value': '226', 'unit': '/255', 'timestamp': '2025-09-02T09:15:11Z', 'ts': '1756804511', 'info': ''}, 'sensor.a2ffffffb_lowbatt': {'sensor_id': 'a2ffffffb', 'gateway_id': '99fffff9d', 'sensor_name': 'A2FFFFFFB', 'measurement': 'lowbatt', 'value': '0', 'unit': '', 'timestamp': '2025-09-02T09:15:11Z', 'ts': '1756804511', 'info': ''}, 'sensor.a2ffffffb_lowbatt_txt': {'sensor_id': 'a2ffffffb', 'gateway_id': '99fffff9d', 'sensor_name': 'A2FFFFFFB', 'measurement': 'lowbatt_text', 'value': '0', 'text': 'No', 'uint': '', 'timestamp': '2025-09-02T09:15:11Z', 'ts': '1756804511'}, 'sensor.a2ffffffb_wind_direction': {'sensor_id': 'a2ffffffb', 'gateway_id': '99fffff9d', 'sensor_name': 'A2FFFFFFB', 'measurement': 'wind_direction', 'value': '8', 'unit': '', 'timestamp': '2025-09-02T09:15:11Z', 'ts': '1756804511', 'info': ''},
        "sensor.a2ffffffb_wind_direction": {
            "sensor_id": "a2ffffffb",
            "gateway_id": "017654321",
            "sensor_name": "A2FFFFFFB",
            "measurement": "wind_direction",
            "value": "8",
            "unit": "°",
            "timestamp": "2025-09-02T09:15:11Z",
            "ts": int(now),
        },
        "sensor.a2ffffffb_wind_direction_deg": {
            "sensor_id": "a2ffffffb",
            "gateway_id": "017654321",
            "sensor_name": "A2FFFFFFB",
            "measurement": "wind_direction_deg",
            "value": "8",
            "unit": "°",
            "timestamp": "2025-09-02T09:15:11Z",
            "ts": int(now),
        },
        "sensor.a2ffffffc_wind_direction_deg": {
            "sensor_id": "a2ffffffc",
            "gateway_id": "017654321",
            "sensor_name": "A2FFFFFFC",
            "measurement": "wind_direction_deg",
            "value": "xxx",
            "unit": "°",
            "timestamp": "2025-09-02T09:15:11Z",
            "ts": int(now),
        },
        "sensor.a2ffffffc_rssi": {
            "sensor_id": "a2ffffffb",
            "gateway_id": "017654321",
            "sensor_name": "A2FFFFFFB",
            "measurement": "rssi",
            "value": "222",
            "unit": "/255",
            "timestamp": "2025-09-02T09:15:11Z",
            "ts": int(now) - 1000000,  # old
        },
        "sensor.a1fffffea_rain": {
            "sensor_id": "a1fffffea",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEA",
            "measurement": "rain_1_hour",
            "value": "7.4",
            "unit": "mm",
            "timestamp": "2025-09-02T07:36:30Z",
            "ts": int(now),
            "reset_rain": False,
        },
        "sensor.a1fffffea_rain_rel": {
            "sensor_id": "a1fffffea",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEA",
            "measurement": "rain_1_hour",
            "value": "7.4",
            "unit": "mm",
            "timestamp": "2025-09-02T07:36:30Z",
            "ts": int(now),
            "reset_rain": True,
        },
        "sensor.a1fffffea_rain_hour": {
            "sensor_id": "a1fffffea",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEA",
            "measurement": "rain_1_hour",
            "value": "7.4",
            "unit": "mm",
            "timestamp": "2025-09-02T07:36:30Z",
            "ts": int(now) - 60,
            "reset_rain": False,
        },
        "sensor.a1fffffec_rain_24hours": {
            "sensor_id": "a1fffffec",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEC",
            "measurement": "rain_24hours",
            "value": "7.4",
            "unit": "mm",
            "timestamp": "2025-09-02T07:36:30Z",
            "ts": int(now) - 60,
            "reset_rain": False,
        },
        "sensor.a1fffffeb_rain_hour": {
            "sensor_id": "a1fffffeb",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEB",
            "measurement": "rain_1_hour",
            "unit": "mm",
            "timestamp": "2025-09-02T07:36:30Z",
            "ts": int(now),
            "reset_rain": True,
        },
        "sensor.a1fffffea_rain_24hours": {
            "sensor_id": "a1fffffea",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEA",
            "measurement": "rain_24_hours",
            "value": "7.4",
            "unit": "mm",
            "timestamp": "2025-09-02T09:36:28Z",
            "ts": int(now),
            "reset_rain": True,  # 224..232
        },
        "sensor.057654321_barometric_pressure": {
            "sensor_id": "057654321",
            "gateway_id": "057654321",
            "sensor_name": "057654321",
            "measurement": "barometric_pressure",
            "value": "1000.1",
            "unit": "hPa",
            "timestamp": "2025-09-02T10:31:42Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.057654322_barometric_pressure": {
            "sensor_id": "057654322",
            "gateway_id": "057654322",
            "sensor_name": "057654322",
            "value": "1000.1",
            "unit": "hPa",
            "timestamp": "2025-09-02T10:31:42Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.057654323_barometric_pressure": {
            "sensor_id": "057654323",
            "gateway_id": "057654323",
            "sensor_name": "057654323",
            "value": "1000.1",
            "timestamp": "2025-09-02T10:31:42Z",
            "ts": int(now),
            "info": "",
        },
    }

    return coordinator


@pytest.fixture
def mock_entry(mock_coordinator):
    """Return a mock ConfigEntry."""
    entry = AsyncMock()  # MagicMock()
    entry.entry_id = "1234"
    entry.runtime_data = mock_coordinator
    return entry


@pytest.fixture
def tfa_me_mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry for a_tfa_me_1 integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_INTERVAL: 30,
            CONF_MULTIPLE_ENTITIES: False,
        },
        unique_id="test-1234",
    )
    entry.add_to_hass(hass)
    return entry


# async def
@pytest.mark.asyncio
async def test_async_setup_entry_adds_entities(
    hass: HomeAssistant, mock_entry, mock_coordinator
) -> None:
    """Test that async_setup_entry correctly adds entities."""
    added_entities = []

    def _async_add_entities(entities, update_before_add=False):
        added_entities.extend(entities)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_entry.entry_id] = mock_entry.runtime_data

    await async_setup_entry(hass, mock_entry, _async_add_entities)

    assert len(added_entities) >= 1
    sensor = added_entities[0]
    assert isinstance(sensor, TFAmeSensorEntity)
    assert sensor.unique_id == "tfame_sensor.a01234567_temperature"
    assert sensor.name == "A01234567 Temperature"


class FailingEntitiesError(Exception):
    """Custom exception for testing."""


async def test_async_setup_entry_raises_config_entry_not_ready(
    hass: HomeAssistant, mock_entry
) -> None:
    """Test setup raises ConfigEntryNotReady on error."""

    def failing_entities(*args, **kwargs):
        raise FailingEntitiesError("failing_entities")

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, mock_entry, failing_entities)


async def test_sensor_entity_properties(mock_coordinator) -> None:
    """Test properties of TFAmeSensorEntity."""
    entity = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="a01234567",
        entity_id="sensor.a01234567_temperature",
    )

    # unique_id
    assert entity.unique_id == "tfame_sensor.a01234567_temperature"

    # name
    assert entity.name == "A01234567 Temperature"

    # measurement_name
    assert entity.measurement_name == "temperature"

    # native_value should return float value
    assert float(entity.native_value) == 23.5

    # unit
    assert entity.native_unit_of_measurement == "°C"

    # attributes
    attrs = entity.extra_state_attributes
    assert attrs["sensor_name"] == "A01234567"
    assert attrs["measurement"] == "temperature"
    assert "timestamp" in attrs
    assert "icon" in attrs
    # Icon
    entity._attr_native_value = 20.0
    assert entity.icon == ICON_MAPPING["temperature"]["default"]

    # Attribute sensor_name = None
    attrs["sensor_name"] = None
    assert attrs["sensor_name"] is None

    del mock_coordinator.data[entity.entity_id]["sensor_name"]
    assert entity.name == "None"

    del mock_coordinator.data[entity.entity_id]["measurement"]
    assert entity.measurement_name is None

    # Humidity
    entity2 = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="a6f169ad1",
        entity_id="sensor.a6f169ad1_humidity",
    )
    assert float(entity2.native_value) == 50.0

    # Rain value
    mock_coordinator.reset_rain_sensors = True
    entity3 = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="a1fffffea",
        entity_id="sensor.a1fffffea_rain_rel",
    )
    assert float(entity3.init_measure_value) == 7.4
    assert float(entity3.native_value) == 0.0

    # Test rain 1 hour
    now = datetime.now().timestamp()
    entity4 = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="a1fffffea",
        entity_id="sensor.a1fffffea_rain_hour",
    )
    assert float(entity4.init_measure_value) == 7.4
    assert entity4.rain_history.max_age == 60 * 60
    assert float(entity4.native_value) == 0.0

    # Add a history for test
    entity4.rain_history.add_measurement(7.4, int(now) - 60)
    entity4.rain_history.add_measurement(8.0, int(now) - 30)
    entity4.rain_history.add_measurement(9.0, int(now))
    assert entity4.rain_history.get_oldest_and_newest() == (
        (7.4, int(now) - 60),
        (9.0, int(now)),
    )
    assert float(entity4.init_measure_value) == 7.4
    await entity4.async_update()
    assert float(entity4.native_value) == 1.6
    # remove value
    del mock_coordinator.data[entity.entity_id]["value"]
    assert float(entity4.native_value) == 1.6

    # Test rain 24 hour
    now = datetime.now().timestamp()
    entity_24 = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="a1fffffec",
        entity_id="sensor.a1fffffec_rain_24hours",
    )
    assert float(entity_24.init_measure_value) == 7.4
    assert entity_24.rain_history_24.max_age == (24 * 60 * 60)
    assert float(entity_24.native_value) == 0.0

    # Add a history for test
    entity_24.rain_history_24.add_measurement(7.4, int(now) - 60)
    entity_24.rain_history_24.add_measurement(8.0, int(now) - 30)
    entity_24.rain_history_24.add_measurement(9.0, int(now))
    assert entity_24.rain_history_24.get_oldest_and_newest() == (
        (7.4, int(now) - 60),
        (9.0, int(now)),
    )
    assert float(entity_24.init_measure_value) == 7.4
    await entity4.async_update()
    assert float(entity_24.native_value) == 1.6

    # Test rain 1 hour (value missing) part 2 : 270...280
    entity4b = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="a1fffffeb",
        entity_id="sensor.a1fffffeb_rain_hour",
    )
    assert entity4b.measure_name == "rain_1_hour"
    assert entity4b.native_value is None

    mock_coordinator.reset_rain_sensors = True
    entity5 = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="a1fffffea",
        entity_id="sensor.a1fffffea_rain_24hours",
    )
    assert float(entity5.init_measure_value) == 7.4
    assert float(entity5.native_value) == 0.0

    # station barometric pressure
    entity6 = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="057654321",
        entity_id="sensor.057654321_barometric_pressure",
    )
    assert float(entity6.native_value) == 1000.1
    # unit None
    mock_coordinator.data[entity.entity_id]["unit"] = None
    assert entity.native_unit_of_measurement is None
    # Remove unit
    del mock_coordinator.data[entity.entity_id]["unit"]
    assert entity.native_unit_of_measurement == ""

    # station barometric pressure without "measurement"
    entity7 = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="057654322",
        entity_id="sensor.057654322_barometric_pressure",
    )
    assert float(entity7.native_value) == 1000.1

    attrs = entity7.extra_state_attributes
    assert attrs == {}

    # station barometric pressure without "unit"
    entity8 = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="057654323",
        entity_id="sensor.057654323_barometric_pressure",
    )
    assert entity8.native_unit_of_measurement == ""

    # mock_coordinator.async_discover_new_entities()
    await mock_coordinator._handle_coordinator_update()
    # assert entity8.native_unit_of_measurement == ""


async def test_wind_sensor(mock_coordinator) -> None:
    """Test wind sensor."""
    entity = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="a2ffffffb",
        entity_id="sensor.a2ffffffb_wind_direction_deg",
    )
    assert entity.name == "A2FFFFFFB Wind direction deg"
    assert entity.native_value == 180.0

    # Invalid sensor ID  & entity ID
    entity_2 = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="a2ffffffa",
        entity_id="sensor.a2ffffffa_wind_direction_deg",
    )
    assert entity_2.native_value is None

    # Invalid value: 306-319
    entity_3 = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="a2ffffffc",
        entity_id="sensor.a2ffffffc_wind_direction_deg",
    )
    assert entity_3.native_value is None

    # Old
    entity_4 = TFAmeSensorEntity(
        coordinator=mock_coordinator,
        sensor_id="a2ffffffc",
        entity_id="sensor.a2ffffffc_rssi",
    )
    assert entity_4.native_value is None
    # wrong id
    assert entity_4.get_timeout("xx") == 0


class DummyEntity:
    """Minimal Entity class for Icons & other tests."""

    def get_icon(self, measurement_type, value_state) -> str:
        """Get the icon."""
        return TFAmeSensorEntity.get_icon(self, measurement_type, value_state)

    def get_rain_icon(self, value) -> str:
        """Get rain icon."""
        return TFAmeSensorEntity.get_rain_icon(self, value)

    def get_wind_direction_icon(self, value) -> str:
        """Get wind direction icon."""
        return TFAmeSensorEntity.get_wind_direction_icon(self, value)

    def format_string_tfa_id(self, s: str, gw_id: str, multiple_entities: bool) -> str:
        """Get sensor names."""
        return TFAmeSensorEntity.format_string_tfa_id(self, s, gw_id, multiple_entities)

    def format_string_tfa_type(self, s: str):
        """Convert string 'xxxxxxxxx' into 'Sensor/station type XX'."""
        return TFAmeSensorEntity.format_string_tfa_type(self, s)


@pytest.fixture
def entity():
    """Dummy icons test entity."""
    return DummyEntity()


def test_temperature_icons(entity) -> None:
    """Test temperature icons."""
    assert entity.get_icon("temperature", -5) == ICON_MAPPING["temperature"]["low"]
    assert entity.get_icon("temperature", 10) == ICON_MAPPING["temperature"]["default"]
    assert entity.get_icon("temperature", 30) == ICON_MAPPING["temperature"]["high"]
    assert entity.get_icon("temperature", None) == "mdi:thermometer"
    assert entity.get_icon("temperature", "xxx") == ICON_MAPPING["temperature"]["low"]


def test_humidity_icons(entity) -> None:
    """Test humidity icons."""
    assert entity.get_icon("humidity", 20) == ICON_MAPPING["humidity"]["alert"]
    assert entity.get_icon("humidity", 50) == ICON_MAPPING["humidity"]["default"]
    assert entity.get_icon("humidity", 70) == ICON_MAPPING["humidity"]["alert"]
    assert entity.get_icon("humidity", None) == ICON_MAPPING["humidity"]["default"]


def test_co2_and_pressure_icons(entity) -> None:
    """Test CO2 and pressure icons."""
    assert entity.get_icon("co2", 500) == ICON_MAPPING["co2"]["default"]
    assert (
        entity.get_icon("barometric_pressure", 1013)
        == ICON_MAPPING["barometric_pressure"]["default"]
    )


def test_rssi_icons(entity) -> None:
    """Test RSSI icons."""
    assert entity.get_icon("rssi", None) == ICON_MAPPING["rssi"]["weak"]
    assert entity.get_icon("rssi", 50) == ICON_MAPPING["rssi"]["weak"]
    assert entity.get_icon("rssi", 120) == ICON_MAPPING["rssi"]["middle"]
    assert entity.get_icon("rssi", 200) == ICON_MAPPING["rssi"]["good"]
    assert entity.get_icon("rssi", 250) == ICON_MAPPING["rssi"]["strong"]


def test_battery_icons(entity) -> None:
    """Test battery icons."""
    assert entity.get_icon("lowbatt", 1) == ICON_MAPPING["lowbatt"]["low"]
    assert entity.get_icon("lowbatt", 0) == ICON_MAPPING["lowbatt"]["full"]


def test_rain_icons(entity) -> None:
    """Test rain icons."""
    assert entity.get_icon("rain", 2) == ICON_MAPPING["rain"]["moderate"]
    assert entity.get_icon("rain_relative", None) == "mdi:help-circle"

    assert entity.get_icon("rain_relative", 0.05) == ICON_MAPPING["rain"]["none"]
    assert entity.get_icon("rain_relative", 0.2) == ICON_MAPPING["rain"]["light"]
    assert entity.get_icon("rain_relative", 2.0) == ICON_MAPPING["rain"]["moderate"]
    assert entity.get_icon("rain_relative", 5.0) == ICON_MAPPING["rain"]["heavy"]


def test_wind_icons(entity) -> None:
    """Test wind icons."""
    assert entity.get_icon("wind_speed", 5) == ICON_MAPPING["wind"]["gust"]
    assert entity.get_icon("wind_gust", 5) == ICON_MAPPING["wind"]["wind"]

    # 16 direction values
    for i in range(15):
        text_dir: str = f"{i}"
        assert entity.get_icon("wind_direction", i) == ICON_MAPPING_WIND_DIR[text_dir]
    assert entity.get_icon("wind_direction", None) == "mdi:compass-outline"
    assert entity.get_icon("wind_direction", 17) == "mdi:compass-outline"


def test_fallback_icon(entity) -> None:
    """Test fallback icons."""
    assert entity.get_icon("unknown_type", 123) == "mdi:help-circle"


def test_multiple_entity(entity) -> None:
    """Test multiple entity OPTION."""
    assert (
        entity.format_string_tfa_id(
            s="A01234567", gw_id="017654321", multiple_entities=True
        )
        == "TFA.me A01-234-567(017654321)"
    )
    assert (
        entity.format_string_tfa_id(
            s="A01234567", gw_id="017654321", multiple_entities=False
        )
        == "TFA.me A01-234-567"
    )


def test_format_string_tfa_type(entity) -> None:
    """Test sensor & stations type XX."""
    for i in range(7):
        type_str: str = f"A{i}"
        assert entity.format_string_tfa_type(type_str) == DEVICE_MAPPING[type_str]
    for i in range(7):
        type_str: str = f"0{i + 1}"
        assert entity.format_string_tfa_type(type_str) == DEVICE_MAPPING[type_str]

    assert entity.format_string_tfa_type("22") == "?"


def test_history_class() -> None:
    """Test history class."""
    hist = SensorHistory(2)  # 2 minutes history
    # test list empty
    assert hist.get_oldest_and_newest() == (None, None)

    now = int(datetime.now().timestamp())
    hist.add_measurement(12.1, now - 180)  # to old, will be reoved
    hist.add_measurement(12.1, now - 120)
    # test get list with one tuple
    assert hist.get_data() == [(12.1, now - 120)]

    hist.add_measurement(12.4, now - 60)
    hist.add_measurement(12.7, now)

    # test get oldest newest
    assert hist.get_oldest_and_newest() == ((12.1, now - 120), (12.7, now))


@pytest.fixture
def mock_config_entry(hass: HomeAssistant, tfa_me_mock_entry) -> ConfigEntry:
    """Create dummy ConfigEntry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.domain = DOMAIN
    entry.data = {}
    entry.runtime_data = TFAmeDataCoordinator(
        hass=hass,
        config_entry=tfa_me_mock_entry,
        host="192.168.1.46",
        interval=timedelta(30),
        multiple_entities=False,
    )
    entry.runtime_data.sensor_entity_list = []
    entry.data = {}
    return entry


@pytest.mark.asyncio
async def test_async_discover_new_entities(
    hass: HomeAssistant, mock_coordinator, mock_config_entry: ConfigEntry
) -> None:
    """Test that async_discover_new_entities adds new entities."""
    now = datetime.now().timestamp()

    # Arrange:
    async_add_entities = AsyncMock()

    # Initial coordinator data, one entity
    entity_id_existing = "sensor.a0f169ad1_temperature"
    mock_coordinator.data = {
        entity_id_existing: {
            "sensor_id": "a0f169ad1",
            "gateway_id": "017654321",
            "sensor_name": "A0F169AD1",
            "measurement": "temperature",
            "value": "24.7",
            "unit": "°C",
            "timestamp": "2025-09-02T09:15:13Z",
            "ts": int(now),
            "info": "",
        },
    }
    mock_coordinator.sensor_entity_list = [entity_id_existing]

    mock_config_entry.runtime_data = mock_coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_config_entry.entry_id] = mock_config_entry

    # Act: Setup Entry -> async_discover_new_entities registers itself
    await async_setup_entry(
        hass, mock_config_entry, async_add_entities
    )  # This is a problem ?

    # Add new "received" data entity to coordinator
    entity_id_new = "sensor.a0f169ad1_humidity"
    mock_coordinator.data[entity_id_new] = {
        "sensor_id": "a0f169ad1",
        "gateway_id": "017654321",
        "sensor_name": "A0F169AD1",
        "measurement": "humidity",
        "value": "55.7",
        "unit": "%",
        "timestamp": "2025-09-02T09:15:13Z",
        "ts": int(now),
        "info": "",
    }

    # Act: Call service function
    await hass.data[DOMAIN][mock_config_entry.entry_id].async_discover_new_entities()

    # Assert: async_add_entities was called again
    assert async_add_entities.call_count == 3

    # Are all entities in list?
    assert hass.data[DOMAIN][
        mock_config_entry.entry_id
    ].runtime_data.sensor_entity_list == [
        "sensor.a0f169ad1_temperature",
        "sensor.a0f169ad1_humidity",
    ]

    # Add new "received" data entity to coordinator
    entity_id_new_2 = "sensor.a27654321_wind_direction_txt"
    mock_coordinator.data[entity_id_new_2] = {
        "sensor_id": "a27654321",
        "gateway_id": "017654321",
        "sensor_name": "a27654321",
        "measurement": "wind_direction_text",
        "value": "0",
        "unit": "",
        "timestamp": "2025-09-02T09:15:13Z",
        "ts": int(now),
        "info": "",
    }

    # Call service function
    await hass.data[DOMAIN][mock_config_entry.entry_id].async_discover_new_entities()

    # Assert: async_add_entities was called again
    assert async_add_entities.call_count == 4

    # Are all entities in list?
    assert hass.data[DOMAIN][
        mock_config_entry.entry_id
    ].runtime_data.sensor_entity_list == [
        "sensor.a0f169ad1_temperature",
        "sensor.a0f169ad1_humidity",
        "sensor.a27654321_wind_direction_txt",
    ]


@pytest.mark.asyncio
async def test_handle_coordinator_update_rain_hour(
    hass: HomeAssistant, tfa_me_mock_entry
) -> None:
    """Test whether rain history is updated for rain_hour."""

    # --- Arrange ---
    coordinator = TFAmeDataCoordinator(
        hass=hass,
        config_entry=tfa_me_mock_entry,
        host="012-345-678",
        interval=timedelta(30),
        multiple_entities=False,
    )

    now = datetime.now().timestamp()
    entity_id_1 = "sensor.a17654321_rain_hour"

    coordinator.data = {
        entity_id_1: {
            "sensor_id": "a1fffffea",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEA",
            "measurement": "rain_1_hour",
            "value": "7.4",
            "unit": "mm",
            "timestamp": "2025-09-02T07:36:30Z",
            "ts": int(now),
            "reset_rain": False,
        }
    }

    # New entity
    entity = TFAmeSensorEntity(
        coordinator, sensor_id="a17654321", entity_id=entity_id_1
    )
    entity.coordinator = coordinator

    # Register entity at hass
    entity.hass = hass
    await entity.async_added_to_hass()

    # rain_history mocken
    entity.rain_history = MagicMock()
    entity.rain_history_24 = MagicMock()

    # --- Act ---
    entity._handle_coordinator_update()
    entity.rain_history.add_measurement.assert_called_once()  #   assert_not_called()

    # Delete value
    del coordinator.data[entity.entity_id]["value"]
    entity._handle_coordinator_update()

    # --- Assert ---
    # entity.rain_history.add_measurement.assert_called_once_with(7.4, int(now))
    entity.rain_history.add_measurement.assert_called_once()


@pytest.mark.asyncio
async def test_handle_coordinator_update_rain_24hours(
    hass: HomeAssistant, tfa_me_mock_entry
) -> None:
    """Test whether rain history is updated for rain_24hours."""

    # --- Arrange ---
    coordinator = TFAmeDataCoordinator(
        hass=hass,
        config_entry=tfa_me_mock_entry,
        host="192.168.1.46",
        interval=timedelta(30),
        multiple_entities=False,
    )

    now = datetime.now().timestamp()
    entity_id_1 = "sensor.a17654321_rain_24hours"

    coordinator.data = {
        entity_id_1: {
            "sensor_id": "a1fffffea",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEA",
            "measurement": "rain_24hours",
            "value": "7.4",
            "unit": "mm",
            "timestamp": "2025-09-02T07:36:30Z",
            "ts": int(now),
            "reset_rain": False,
        }
    }

    # New entity
    entity = TFAmeSensorEntity(
        coordinator, sensor_id="a17654321", entity_id=entity_id_1
    )
    entity.coordinator = coordinator

    # Register entity at hass
    entity.hass = hass
    await entity.async_added_to_hass()

    # rain_history mocken
    entity.rain_history = MagicMock()
    entity.rain_history_24 = MagicMock()

    # --- Act ---
    entity._handle_coordinator_update()
    entity.rain_history_24.add_measurement.assert_called_once_with(str(7.4), int(now))

    del coordinator.data[entity.entity_id]["value"]
    entity._handle_coordinator_update()

    # --- Assert ---
    # entity.rain_history.add_measurement.assert_called_once_with(7.4, int(now))
    entity.rain_history_24.add_measurement.assert_called_once()


@pytest.mark.asyncio
async def test_async_update_triggers_refresh() -> None:
    """Test async_update()."""
    # Arrange
    mock_coordinator = AsyncMock()
    entity = TFAmeSensorEntity(mock_coordinator, "abc", "sensor.abc_temp")

    # Act
    await entity.async_update()

    # Assert
    mock_coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_mdns_success(hass: HomeAssistant, tfa_me_mock_entry) -> None:
    """Test."""
    coordinator = TFAmeDataCoordinator(
        hass, tfa_me_mock_entry, "012-345-678", timedelta(seconds=10), True
    )

    with patch("socket.gethostbyname", return_value="192.168.1.10"):
        result = await coordinator.resolve_mdns("tfa-me-012-345-678.local")

    assert result == "192.168.1.10"


@pytest.mark.asyncio
async def test_resolve_mdns_failure(hass: HomeAssistant, tfa_me_mock_entry) -> None:
    """Test."""
    coordinator = TFAmeDataCoordinator(
        hass, tfa_me_mock_entry, "test-host", timedelta(seconds=10), True
    )

    with patch("socket.gethostbyname", side_effect=socket.gaierror):
        result = await coordinator.resolve_mdns("127.0.0.1")

    # Fallback: hostname not changed
    assert result == "127.0.0.1"
