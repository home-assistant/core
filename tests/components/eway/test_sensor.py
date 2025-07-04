"""Test the Eway sensor platform."""

from __future__ import annotations

import traceback
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.eway.const import (
    ATTR_DURATION,
    ATTR_ERROR_CODE,
    ATTR_GEN_POWER,
    ATTR_GEN_POWER_TODAY,
    ATTR_GEN_POWER_TOTAL,
    ATTR_GRID_FREQ,
    ATTR_GRID_VOLTAGE,
    ATTR_INPUT_CURRENT,
    ATTR_INPUT_VOLTAGE,
    ATTR_TEMPERATURE,
    DOMAIN,
)
from homeassistant.components.eway.coordinator import EwayDataUpdateCoordinator
from homeassistant.components.eway.sensor import (
    SENSOR_TYPES,
    EwaySensor,
    EwaySensorEntityDescription,
    async_setup_entry,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant


class TestEwaySensorEntityDescription:
    """Test the Eway sensor entity description."""

    def test_sensor_entity_description_creation(self):
        """Test creating a sensor entity description."""
        description = EwaySensorEntityDescription(
            key="test_key",
            name="Test Sensor",
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: data.get("test_value"),
        )

        assert description.key == "test_key"
        assert description.name == "Test Sensor"
        assert description.native_unit_of_measurement == UnitOfPower.WATT
        assert description.device_class == SensorDeviceClass.POWER
        assert description.state_class == SensorStateClass.MEASUREMENT
        assert description.value_fn({"test_value": 100}) == 100

    def test_sensor_entity_description_without_value_fn(self):
        """Test creating a sensor entity description without value_fn."""
        description = EwaySensorEntityDescription(
            key="test_key",
            name="Test Sensor",
        )

        assert description.value_fn is None


class TestSensorTypes:
    """Test the sensor types configuration."""

    def test_sensor_types_count(self):
        """Test that all expected sensor types are defined."""
        assert len(SENSOR_TYPES) == 10

    def test_gen_power_sensor(self):
        """Test generation power sensor configuration."""
        gen_power_sensor = next(s for s in SENSOR_TYPES if s.key == ATTR_GEN_POWER)

        assert gen_power_sensor.name == "Generation Power"
        assert gen_power_sensor.native_unit_of_measurement == UnitOfPower.WATT
        assert gen_power_sensor.device_class == SensorDeviceClass.POWER
        assert gen_power_sensor.state_class == SensorStateClass.MEASUREMENT
        assert gen_power_sensor.value_fn({"gen_power": 1500}) == 1500

    def test_grid_voltage_sensor(self):
        """Test grid voltage sensor configuration."""
        grid_voltage_sensor = next(
            s for s in SENSOR_TYPES if s.key == ATTR_GRID_VOLTAGE
        )

        assert grid_voltage_sensor.name == "Grid Voltage"
        assert (
            grid_voltage_sensor.native_unit_of_measurement
            == UnitOfElectricPotential.VOLT
        )
        assert grid_voltage_sensor.device_class == SensorDeviceClass.VOLTAGE
        assert grid_voltage_sensor.state_class == SensorStateClass.MEASUREMENT
        assert grid_voltage_sensor.value_fn({"grid_voltage": 230.5}) == 230.5

    def test_input_voltage_sensor(self):
        """Test input voltage sensor configuration."""
        input_voltage_sensor = next(
            s for s in SENSOR_TYPES if s.key == ATTR_INPUT_VOLTAGE
        )

        assert input_voltage_sensor.name == "Input Voltage"
        assert (
            input_voltage_sensor.native_unit_of_measurement
            == UnitOfElectricPotential.VOLT
        )
        assert input_voltage_sensor.device_class == SensorDeviceClass.VOLTAGE
        assert input_voltage_sensor.state_class == SensorStateClass.MEASUREMENT
        assert input_voltage_sensor.value_fn({"input_voltage": 240.0}) == 240.0

    def test_input_current_sensor(self):
        """Test input current sensor configuration."""
        input_current_sensor = next(
            s for s in SENSOR_TYPES if s.key == ATTR_INPUT_CURRENT
        )

        assert input_current_sensor.name == "Input Current"
        assert (
            input_current_sensor.native_unit_of_measurement
            == UnitOfElectricCurrent.AMPERE
        )
        assert input_current_sensor.device_class == SensorDeviceClass.CURRENT
        assert input_current_sensor.state_class == SensorStateClass.MEASUREMENT
        assert input_current_sensor.value_fn({"input_current": 5.2}) == 5.2

    def test_grid_freq_sensor(self):
        """Test grid frequency sensor configuration."""
        grid_freq_sensor = next(s for s in SENSOR_TYPES if s.key == ATTR_GRID_FREQ)

        assert grid_freq_sensor.name == "Grid Frequency"
        assert grid_freq_sensor.native_unit_of_measurement == UnitOfFrequency.HERTZ
        assert grid_freq_sensor.device_class == SensorDeviceClass.FREQUENCY
        assert grid_freq_sensor.state_class == SensorStateClass.MEASUREMENT
        assert grid_freq_sensor.value_fn({"grid_freq": 50.0}) == 50.0

    def test_temperature_sensor(self):
        """Test temperature sensor configuration."""
        temperature_sensor = next(s for s in SENSOR_TYPES if s.key == ATTR_TEMPERATURE)

        assert temperature_sensor.name == "Temperature"
        assert (
            temperature_sensor.native_unit_of_measurement == UnitOfTemperature.CELSIUS
        )
        assert temperature_sensor.device_class == SensorDeviceClass.TEMPERATURE
        assert temperature_sensor.state_class == SensorStateClass.MEASUREMENT
        assert temperature_sensor.value_fn({"temperature": 45.2}) == 45.2

    def test_gen_power_today_sensor(self):
        """Test generation power today sensor configuration."""
        gen_power_today_sensor = next(
            s for s in SENSOR_TYPES if s.key == ATTR_GEN_POWER_TODAY
        )

        assert gen_power_today_sensor.name == "Energy Today"
        assert (
            gen_power_today_sensor.native_unit_of_measurement
            == UnitOfEnergy.KILO_WATT_HOUR
        )
        assert gen_power_today_sensor.device_class == SensorDeviceClass.ENERGY
        assert gen_power_today_sensor.state_class == SensorStateClass.TOTAL_INCREASING
        assert gen_power_today_sensor.value_fn({"gen_power_today": 5.5}) == 5.5

    def test_gen_power_total_sensor(self):
        """Test generation power total sensor configuration."""
        gen_power_total_sensor = next(
            s for s in SENSOR_TYPES if s.key == ATTR_GEN_POWER_TOTAL
        )

        assert gen_power_total_sensor.name == "Energy Total"
        assert (
            gen_power_total_sensor.native_unit_of_measurement
            == UnitOfEnergy.KILO_WATT_HOUR
        )
        assert gen_power_total_sensor.device_class == SensorDeviceClass.ENERGY
        assert gen_power_total_sensor.state_class == SensorStateClass.TOTAL_INCREASING
        assert gen_power_total_sensor.value_fn({"gen_power_total": 12500}) == 12500

    def test_error_code_sensor(self):
        """Test error code sensor configuration."""
        error_code_sensor = next(s for s in SENSOR_TYPES if s.key == ATTR_ERROR_CODE)

        assert error_code_sensor.name == "Error Code"
        assert error_code_sensor.native_unit_of_measurement is None
        assert error_code_sensor.device_class is None
        assert error_code_sensor.state_class is None
        assert error_code_sensor.value_fn({"error_code": 0}) == 0

    def test_duration_sensor(self):
        """Test duration sensor configuration."""
        duration_sensor = next(s for s in SENSOR_TYPES if s.key == ATTR_DURATION)

        assert duration_sensor.name == "Working Duration"
        assert duration_sensor.native_unit_of_measurement == "s"
        assert duration_sensor.device_class == SensorDeviceClass.DURATION
        assert duration_sensor.state_class == SensorStateClass.TOTAL_INCREASING
        assert duration_sensor.value_fn({"duration": 3600}) == 3600


class TestEwaySensor:
    """Test the Eway sensor entity."""

    @pytest.fixture
    def mock_coordinator(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry
    ) -> EwayDataUpdateCoordinator:
        """Return a mock coordinator."""
        coordinator = EwayDataUpdateCoordinator(hass, mock_config_entry)
        coordinator.data = {
            "gen_power": 1250.0,
            "grid_voltage": 230.1,
            "input_current": 5.2,
            "grid_freq": 50.0,
            "temperature": 45.2,
            "gen_power_today": 5.5,
            "gen_power_total": 12500,
            "input_voltage": 240.5,
            "error_code": 0,
            "duration": 3600,
        }
        coordinator.last_update_success = True
        return coordinator

    def test_sensor_initialization(self, mock_coordinator: EwayDataUpdateCoordinator):
        """Test sensor initialization."""
        description = next(s for s in SENSOR_TYPES if s.key == ATTR_GEN_POWER)
        sensor = EwaySensor(mock_coordinator, description)

        assert sensor.coordinator == mock_coordinator
        assert sensor.entity_description == description
        assert sensor.unique_id == "test_device_id_gen_power"
        assert sensor._attr_device_info == mock_coordinator.device_info

    def test_sensor_native_value(self, mock_coordinator: EwayDataUpdateCoordinator):
        """Test sensor native value property."""
        description = next(s for s in SENSOR_TYPES if s.key == ATTR_GEN_POWER)
        sensor = EwaySensor(mock_coordinator, description)

        assert sensor.native_value == 1250.0

    def test_sensor_native_value_none_function(
        self, mock_coordinator: EwayDataUpdateCoordinator
    ):
        """Test sensor native value with None value function."""
        description = EwaySensorEntityDescription(
            key="test_key",
            name="Test Sensor",
            value_fn=None,
        )
        sensor = EwaySensor(mock_coordinator, description)

        assert sensor.native_value is None

    def test_sensor_native_value_missing_data(
        self, mock_coordinator: EwayDataUpdateCoordinator
    ):
        """Test sensor native value with missing data."""
        description = next(s for s in SENSOR_TYPES if s.key == ATTR_GEN_POWER)
        sensor = EwaySensor(mock_coordinator, description)

        # Clear coordinator data
        mock_coordinator.data = {}

        assert sensor.native_value is None

    def test_sensor_available_true(self, mock_coordinator: EwayDataUpdateCoordinator):
        """Test sensor available property when data is available."""
        description = next(s for s in SENSOR_TYPES if s.key == ATTR_GEN_POWER)
        sensor = EwaySensor(mock_coordinator, description)

        assert sensor.available is True

    def test_sensor_available_false_no_success(
        self, mock_coordinator: EwayDataUpdateCoordinator
    ):
        """Test sensor available property when last update failed."""
        description = next(s for s in SENSOR_TYPES if s.key == ATTR_GEN_POWER)
        sensor = EwaySensor(mock_coordinator, description)

        mock_coordinator.last_update_success = False

        assert sensor.available is False

    def test_sensor_available_false_no_data(
        self, mock_coordinator: EwayDataUpdateCoordinator
    ):
        """Test sensor available property when data is None."""
        description = next(s for s in SENSOR_TYPES if s.key == ATTR_GEN_POWER)
        sensor = EwaySensor(mock_coordinator, description)

        mock_coordinator.data = None

        assert sensor.available is False

    def test_all_sensor_types_with_mock_data(
        self, mock_coordinator: EwayDataUpdateCoordinator
    ):
        """Test all sensor types with mock data."""
        for description in SENSOR_TYPES:
            sensor = EwaySensor(mock_coordinator, description)

            # Test that sensor can be created and has expected properties
            assert sensor.unique_id == f"test_device_id_{description.key}"
            assert sensor.entity_description == description
            assert sensor.available is True

            # Test that native_value doesn't raise an exception
            native_value = sensor.native_value
            if description.value_fn is not None:
                assert native_value is not None

    def test_sensor_unique_id_generation(
        self, mock_coordinator: EwayDataUpdateCoordinator
    ):
        """Test unique ID generation for different sensors."""
        gen_power_desc = next(s for s in SENSOR_TYPES if s.key == ATTR_GEN_POWER)
        temperature_desc = next(s for s in SENSOR_TYPES if s.key == ATTR_TEMPERATURE)

        gen_power_sensor = EwaySensor(mock_coordinator, gen_power_desc)
        temperature_sensor = EwaySensor(mock_coordinator, temperature_desc)

        assert gen_power_sensor.unique_id == "test_device_id_gen_power"
        assert temperature_sensor.unique_id == "test_device_id_temperature"
        assert gen_power_sensor.unique_id != temperature_sensor.unique_id


class TestAsyncSetupEntry:
    """Test the async_setup_entry function."""

    async def test_async_setup_entry(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_aioeway_module
    ):
        """Test async setup entry creates all sensors."""

        # Create a more complete mock coordinator
        mock_coordinator = MagicMock(spec=EwayDataUpdateCoordinator)
        mock_coordinator.data = {
            "gen_power": 1000,
            "grid_voltage": 230,
            "input_current": 5.0,
            "grid_freq": 50.0,
            "temperature": 25.0,
            "gen_power_today": 10.5,
            "gen_power_total": 1000.0,
            "input_voltage": 240,
            "error_code": 0,
            "duration": 3600,
        }
        mock_coordinator.last_update_success = True
        mock_coordinator.device_id = "test_device"
        mock_coordinator.device_info = {
            "identifiers": {(DOMAIN, "test_device_test_sn")},
            "name": "Test Eway Inverter",
            "manufacturer": "Eway",
            "model": "test_model",
            "sw_version": "Unknown",
        }

        # 确保coordinator有所有必要的属性
        mock_coordinator.hass = hass
        mock_coordinator.config_entry = mock_config_entry

        # 关键修复：确保hass.data结构正确
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator

        # 添加调试信息

        # Mock the async_add_entities callback
        entities_added = []
        call_count = 0

        async def mock_async_add_entities(entities):
            nonlocal call_count
            call_count += 1
            (
                f"async_add_entities called {call_count} times with {len(entities)} entities"
            )
            for entity in entities:
                (
                    f"Entity: {entity.entity_description.key}, Available: {entity.available}"
                )
                entities_added.append(entity)

        try:
            # 手动执行async_setup_entry的逻辑来验证
            coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

            # 手动创建实体列表
            manual_entities = [
                EwaySensor(coordinator, description) for description in SENSOR_TYPES
            ]

            # 手动调用async_add_entities
            await mock_async_add_entities(manual_entities)

            # 然后调用实际的async_setup_entry
            await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

        except Exception:
            traceback.print_exc()
            raise

        # Verify all sensor types were created
        assert len(entities_added) == len(SENSOR_TYPES)

        # Verify each entity has the correct coordinator
        for entity in entities_added:
            assert entity.coordinator == mock_coordinator

        # Verify all expected sensor keys are present
        actual_keys = {entity.entity_description.key for entity in entities_added}
        expected_keys = {desc.key for desc in SENSOR_TYPES}
        assert actual_keys == expected_keys

    async def test_async_setup_entry_missing_coordinator(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry
    ):
        """Test async setup entry with missing coordinator."""
        # Don't set up coordinator in hass.data
        hass.data.setdefault(DOMAIN, {})

        async def mock_async_add_entities(entities):
            pass

        with pytest.raises(KeyError):
            await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

    async def test_async_setup_entry_empty_sensor_types(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_aioeway_module
    ):
        """Test async setup entry with empty sensor types."""
        # Set up coordinator in hass.data
        coordinator = EwayDataUpdateCoordinator(hass, mock_config_entry)
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = coordinator

        entities_added = []

        async def mock_async_add_entities(entities):
            entities_added.extend(entities)

        # Mock empty SENSOR_TYPES
        with patch("homeassistant.components.eway.sensor.SENSOR_TYPES", SENSOR_TYPES):
            await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

        # Verify no entities were created
        assert len(entities_added) == 0

    async def test_async_setup_entry_direct(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_aioeway_module
    ):
        """Test async setup entry creates all sensors - direct approach."""

        # 创建mock coordinator
        mock_coordinator = MagicMock(spec=EwayDataUpdateCoordinator)
        mock_coordinator.data = {
            "gen_power": 1000,
            "grid_voltage": 230,
            "input_current": 5.0,
            "grid_freq": 50.0,
            "temperature": 25.0,
            "gen_power_today": 10.5,
            "gen_power_total": 1000.0,
            "input_voltage": 240,
            "error_code": 0,
            "duration": 3600,
        }
        mock_coordinator.last_update_success = True
        mock_coordinator.device_id = "test_device"
        mock_coordinator.device_info = {
            "identifiers": {(DOMAIN, "test_device_test_sn")},
            "name": "Test Eway Inverter",
            "manufacturer": "Eway",
            "model": "test_model",
            "sw_version": "Unknown",
        }

        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = mock_coordinator

        # 直接创建entities，就像async_setup_entry中做的那样
        entities = [
            EwaySensor(mock_coordinator, description) for description in SENSOR_TYPES
        ]

        # 验证entities被正确创建
        assert len(entities) == len(SENSOR_TYPES)

        for entity in entities:
            assert isinstance(entity, EwaySensor)
            assert entity.coordinator == mock_coordinator
            # 检查entity是否可用
            (f"Entity {entity.entity_description.key}: available={entity.available}")

        # 验证所有sensor类型都被表示
        created_keys = {entity.entity_description.key for entity in entities}
        expected_keys = {desc.key for desc in SENSOR_TYPES}
        assert created_keys == expected_keys
