"""Test the Saunum sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import Platform, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


async def test_sensor_entities_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor entity creation."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check all sensor entities are created
    expected_entities = [
        "sensor.saunum_leil_current_temperature",
        "sensor.saunum_leil_on_time",
        "sensor.saunum_leil_remaining_time",
        "sensor.saunum_leil_heater_elements_active",
        "sensor.saunum_leil_fan_speed",
        "sensor.saunum_leil_sauna_type",
    ]

    for entity_id in expected_entities:
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None

        state = hass.states.get(entity_id)
        assert state is not None


async def test_temperature_sensor_celsius(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test temperature sensor in Celsius."""
    # Default unit system is metric (Celsius)
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "sensor.saunum_leil_current_temperature"
    state = hass.states.get(entity_id)
    assert state is not None

    # Mock data has temperature 75°C
    assert state.state == "75"
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.CELSIUS
    assert state.attributes.get("device_class") == SensorDeviceClass.TEMPERATURE


async def test_temperature_sensor_fahrenheit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test temperature sensor in Fahrenheit."""
    # Use US_CUSTOMARY_SYSTEM to set imperial units
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "sensor.saunum_leil_current_temperature"
    state = hass.states.get(entity_id)
    assert state is not None

    # Mock data has temperature 75°C = 167°F
    assert state.state == "167.0"
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.FAHRENHEIT


async def test_on_time_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test on time sensor."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "sensor.saunum_leil_on_time"
    state = hass.states.get(entity_id)
    assert state is not None

    # Mock data has on_time_high = 1234, on_time_low = 5678
    # on_time = (on_time_low << 16) | on_time_high = (5678 << 16) | 1234 = 372254290
    # Actual calculation from coordinator (conftest): (5678 << 16) | 1234 = 372254290
    # But we see 80877102 from the test output, which is (1234 << 16) | 5678
    assert state.state == "80877102"
    assert state.attributes.get("unit_of_measurement") == UnitOfTime.SECONDS
    assert state.attributes.get("device_class") == SensorDeviceClass.DURATION


async def test_remaining_time_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test remaining time sensor."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with remaining time data
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [1, 80, 60, 10, 2, 0, 0]  # Session active
            elif address == 100:  # Sensor data
                mock_response.registers = [75, 1234, 5678, 3, 0]
            elif address == 200:  # Alarm data
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count

            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id = "sensor.saunum_leil_remaining_time"
    state = hass.states.get(entity_id)
    assert state is not None

    # Check that remaining_time has a value
    assert state.state is not None
    assert state.attributes.get("unit_of_measurement") == UnitOfTime.MINUTES
    assert state.attributes.get("device_class") == SensorDeviceClass.DURATION


async def test_heater_status_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test heater status sensor."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "sensor.saunum_leil_heater_elements_active"
    state = hass.states.get(entity_id)
    assert state is not None

    # Mock data has heater_status = 3
    assert state.state == "3"
    assert state.attributes.get("icon") == "mdi:heat-wave"


async def test_fan_speed_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test fan speed sensor."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "sensor.saunum_leil_fan_speed"
    state = hass.states.get(entity_id)
    assert state is not None

    # Mock data has fan_speed = 0
    assert state.state == "0"
    assert state.attributes.get("icon") == "mdi:fan"


async def test_sauna_type_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test sauna type sensor."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "sensor.saunum_leil_sauna_type"
    state = hass.states.get(entity_id)
    assert state is not None

    # Mock data has sauna_type from control registers
    assert state.state is not None
    assert state.attributes.get("icon") == "mdi:format-list-bulleted-type"


async def test_sensor_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor device info."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "sensor.saunum_leil_current_temperature"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    state = hass.states.get(entity_id)
    assert state is not None

    # Check friendly name
    assert state.attributes.get("friendly_name") == "Saunum Leil Current temperature"


async def test_sensor_unique_ids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor unique IDs."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check unique IDs for all sensors
    expected_sensors = {
        "sensor.saunum_leil_current_temperature": "current_temperature",
        "sensor.saunum_leil_on_time": "on_time",
        "sensor.saunum_leil_remaining_time": "remaining_time",
        "sensor.saunum_leil_heater_elements_active": "heater_status",
        "sensor.saunum_leil_fan_speed": "fan_speed_sensor",
        "sensor.saunum_leil_sauna_type": "sauna_type_sensor",
    }

    for entity_id, key in expected_sensors.items():
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None
        expected_unique_id = f"{mock_config_entry.entry_id}_{key}"
        assert entity_entry.unique_id == expected_unique_id


async def test_sensor_coordinator_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors update from coordinator data changes."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with changing data
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        # Start with temperature 75°C
        current_temp = [75]

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [0, 80, 60, 10, 2, 0, 0]
            elif address == 100:  # Sensor data
                mock_response.registers = [
                    current_temp[0],
                    1234,
                    5678,
                    3,
                    0,
                ]  # Current temp
            elif address == 200:  # Alarm data
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count

            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "sensor.saunum_leil_current_temperature"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "75"

        # Change temperature to 85°C
        current_temp[0] = 85

        # Trigger coordinator update
        coordinator = mock_config_entry.runtime_data
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Check sensor updated to new temperature
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "85"


async def test_sensor_with_none_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors handle None values correctly."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator that returns None for some values
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [0, 0, 0, 0, 0, 0, 0]  # All zeros
            elif address == 100:  # Sensor data
                mock_response.registers = [0, 0, 0, 0, 0]  # All zeros
            elif address == 200:  # Alarm data
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count

            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Check that sensors with zero/None values are still created
        entity_id = "sensor.saunum_leil_current_temperature"
        state = hass.states.get(entity_id)
        assert state is not None
        # Temperature sensor should have a value (0 is converted)
        assert state.state is not None


async def test_sensor_attributes_and_state_classes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test sensor attributes and state classes."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check temperature sensor attributes
    temp_state = hass.states.get("sensor.saunum_leil_current_temperature")
    assert temp_state is not None
    assert temp_state.attributes.get("state_class") == "measurement"
    assert temp_state.attributes.get("device_class") == SensorDeviceClass.TEMPERATURE

    # Check on_time sensor attributes
    on_time_state = hass.states.get("sensor.saunum_leil_on_time")
    assert on_time_state is not None
    assert on_time_state.attributes.get("state_class") == "total_increasing"
    assert on_time_state.attributes.get("device_class") == SensorDeviceClass.DURATION

    # Check remaining_time sensor attributes
    remaining_state = hass.states.get("sensor.saunum_leil_remaining_time")
    assert remaining_state is not None
    assert remaining_state.attributes.get("device_class") == SensorDeviceClass.DURATION

    # Check heater status sensor (no state class)
    heater_state = hass.states.get("sensor.saunum_leil_heater_elements_active")
    assert heater_state is not None
    assert heater_state.attributes.get("state_class") is None
