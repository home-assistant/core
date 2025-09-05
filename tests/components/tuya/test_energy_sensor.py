"""Test Tuya energy sensor with incremental mode."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from tuya_sharing import CustomerDevice

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.tuya import ManagerCompat
from homeassistant.components.tuya.const import (
    ENERGY_REPORT_MODE_CUMULATIVE,
    ENERGY_REPORT_MODE_INCREMENTAL,
)
from homeassistant.components.tuya.sensor import (
    TuyaEnergySensorEntity,
    TuyaSensorEntityDescription,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_energy_device() -> CustomerDevice:
    """Create a mock energy device for testing."""
    device = MagicMock(spec=CustomerDevice)
    device.id = "test_energy_device_123"
    device.name = "Test Energy Device"
    device.category = "dlq"  # Energy meter category
    device.status = {
        "total_forward_energy": "1000.5",  # kWh
        "cur_current": "5.2",  # A
        "cur_power": "1200",  # W
        "cur_voltage": "230",  # V
    }
    return device


@pytest.fixture
def mock_energy_description() -> TuyaSensorEntityDescription:
    """Create a mock energy sensor description."""
    return TuyaSensorEntityDescription(
        key="total_forward_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    )


@pytest.fixture
def mock_config_entry_with_incremental() -> MockConfigEntry:
    """Create a mock config entry with incremental energy mode."""
    return MockConfigEntry(
        title="Test Tuya Energy",
        domain="tuya",
        data={
            "endpoint": "test_endpoint",
            "terminal_id": "test_terminal",
            "token_info": "test_token",
            "user_code": "test_user_code",
        },
        unique_id="test_energy_123",
        options={
            "device_energy_modes": {
                "test_energy_device_123": ENERGY_REPORT_MODE_INCREMENTAL
            }
        },
    )


@pytest.fixture
def mock_config_entry_with_cumulative() -> MockConfigEntry:
    """Create a mock config entry with cumulative energy mode."""
    return MockConfigEntry(
        title="Test Tuya Energy",
        domain="tuya",
        data={
            "endpoint": "test_endpoint",
            "terminal_id": "test_terminal",
            "token_info": "test_token",
            "user_code": "test_user_code",
        },
        unique_id="test_energy_123",
        options={
            "device_energy_modes": {
                "test_energy_device_123": ENERGY_REPORT_MODE_CUMULATIVE
            }
        },
    )


@pytest.fixture
def mock_manager() -> ManagerCompat:
    """Create a mock Tuya manager."""
    manager = MagicMock(spec=ManagerCompat)
    manager.device_map = {}
    return manager


class TestTuyaEnergySensorEntity:
    """Test TuyaEnergySensorEntity class."""

    def test_init(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test entity initialization."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        assert entity._config_entry == mock_config_entry_with_incremental
        assert entity._cumulative_total == Decimal(0)
        assert entity._last_update_time is None
        assert entity._last_raw_value is None

    def test_is_incremental_mode_true(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test incremental mode detection when configured."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        assert entity._is_incremental_mode is True

    def test_is_incremental_mode_false(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_cumulative,
        mock_manager,
    ):
        """Test incremental mode detection when not configured."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_cumulative,
        )

        assert entity._is_incremental_mode is False

    def test_is_incremental_mode_default(
        self, mock_energy_device, mock_energy_description, mock_manager
    ):
        """Test incremental mode detection with default configuration."""
        config_entry = MockConfigEntry(
            title="Test Tuya Energy",
            domain="tuya",
            data={
                "endpoint": "test_endpoint",
                "terminal_id": "test_terminal",
                "token_info": "test_token",
                "user_code": "test_user_code",
            },
            unique_id="test_energy_123",
        )

        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            config_entry,
        )

        assert entity._is_incremental_mode is False

    @patch("homeassistant.components.tuya.sensor.TuyaSensorEntity.async_added_to_hass")
    async def test_async_added_to_hass_no_restore(
        self,
        mock_super,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
        hass: HomeAssistant,
    ):
        """Test async_added_to_hass without restore state."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Mock no restore state
        with patch.object(entity, "async_get_last_state", return_value=None):
            await entity.async_added_to_hass()

        mock_super.assert_called_once()
        assert entity._cumulative_total == Decimal(0)
        assert entity._last_update_time is None
        assert entity._last_raw_value is None

    @patch("homeassistant.components.tuya.sensor.TuyaSensorEntity.async_added_to_hass")
    async def test_async_added_to_hass_with_restore(
        self,
        mock_super,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
        hass: HomeAssistant,
    ):
        """Test async_added_to_hass with restore state."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Mock restore state
        mock_state = MagicMock()
        mock_state.state = "1500.75"
        mock_state.attributes = {
            "cumulative_total": "1500.75",
            "last_update_time": "1234567890",
            "last_raw_value": "25.5",
        }

        with patch.object(entity, "async_get_last_state", return_value=mock_state):
            await entity.async_added_to_hass()

        mock_super.assert_called_once()
        assert entity._cumulative_total == Decimal("1500.75")
        assert entity._last_update_time == 1234567890
        assert entity._last_raw_value == Decimal("25.5")

    @patch("homeassistant.components.tuya.sensor.TuyaSensorEntity.async_added_to_hass")
    async def test_async_added_to_hass_restore_invalid_values(
        self,
        mock_super,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
        hass: HomeAssistant,
    ):
        """Test async_added_to_hass with invalid restore values."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Mock restore state with invalid values
        mock_state = MagicMock()
        mock_state.state = "invalid"
        mock_state.attributes = {
            "cumulative_total": "invalid",
            "last_update_time": "invalid",
            "last_raw_value": "invalid",
        }

        with patch.object(entity, "async_get_last_state", return_value=mock_state):
            await entity.async_added_to_hass()

        mock_super.assert_called_once()
        # Should fall back to defaults
        assert entity._cumulative_total == Decimal(0)
        assert entity._last_update_time is None
        assert entity._last_raw_value is None

    @patch("homeassistant.components.tuya.sensor.TuyaSensorEntity.async_added_to_hass")
    async def test_async_added_to_hass_restore_missing_attributes(
        self,
        mock_super,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
        hass: HomeAssistant,
    ):
        """Test async_added_to_hass with missing restore attributes."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Mock restore state with missing attributes
        mock_state = MagicMock()
        mock_state.state = "1000.0"
        mock_state.attributes = {}

        with patch.object(entity, "async_get_last_state", return_value=mock_state):
            await entity.async_added_to_hass()

        mock_super.assert_called_once()
        # Should fall back to defaults
        assert entity._cumulative_total == Decimal(0)
        assert entity._last_update_time is None
        assert entity._last_raw_value is None

    @patch("homeassistant.components.tuya.sensor.TuyaSensorEntity._handle_state_update")
    async def test_handle_state_update_no_properties(
        self,
        mock_super,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test _handle_state_update with no updated properties."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        await entity._handle_state_update(None, None)

        mock_super.assert_called_once_with(None, None)

    @patch("homeassistant.components.tuya.sensor.TuyaSensorEntity._handle_state_update")
    async def test_handle_state_update_other_properties(
        self,
        mock_super,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test _handle_state_update with other properties updated."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        await entity._handle_state_update(["cur_current", "cur_power"], None)

        mock_super.assert_called_once_with(["cur_current", "cur_power"], None)

    @patch("homeassistant.components.tuya.sensor.TuyaSensorEntity._handle_state_update")
    @patch.object(TuyaEnergySensorEntity, "_process_incremental_update")
    async def test_handle_state_update_energy_property(
        self,
        mock_process,
        mock_super,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test _handle_state_update with energy property updated."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        await entity._handle_state_update(
            ["total_forward_energy"], {"total_forward_energy": 1234567890}
        )

        mock_process.assert_called_once_with(1234567890)
        mock_super.assert_called_once_with(
            ["total_forward_energy"], {"total_forward_energy": 1234567890}
        )

    def test_process_incremental_update_invalid_cases(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test _process_incremental_update with invalid raw values."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Test with None raw value - this should not accumulate
        with patch.object(
            entity.__class__.__bases__[0],
            "native_value",
            new_callable=PropertyMock,
            return_value=None,
        ):
            entity._process_incremental_update(1234567890)
        assert entity._cumulative_total == Decimal(0)

        # Test with invalid raw value (non-numeric string) - this should not accumulate
        with patch.object(
            entity.__class__.__bases__[0],
            "native_value",
            new_callable=PropertyMock,
            return_value="invalid",
        ):
            entity._process_incremental_update(1234567890)
        assert entity._cumulative_total == Decimal(0)

        # Test with negative raw value - this should not accumulate
        with patch.object(
            entity.__class__.__bases__[0],
            "native_value",
            new_callable=PropertyMock,
            return_value="-5.0",
        ):
            entity._process_incremental_update(1234567890)
        assert entity._cumulative_total == Decimal(0)

    def test_process_incremental_update_valid_value_with_timestamp(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test _process_incremental_update with valid value and timestamp."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Test the _is_new_update method directly
        result = entity._is_new_update(Decimal("25.5"), 1234567890)

        assert result is True
        assert entity._last_update_time == 1234567890
        assert entity._last_raw_value == Decimal("25.5")

    def test_process_incremental_update_valid_value_without_timestamp(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test _process_incremental_update with valid value without timestamp."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Test the _is_new_update method directly without timestamp
        with patch("time.time", return_value=1234567.0):
            result = entity._is_new_update(Decimal("30.0"), None)

        assert result is True
        assert entity._last_update_time == 1234567000  # milliseconds
        assert entity._last_raw_value == Decimal("30.0")

    def test_process_incremental_update_duplicate_timestamp(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test _process_incremental_update with duplicate timestamp."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Set initial values
        entity._last_update_time = 1234567890
        entity._last_raw_value = Decimal("25.5")
        entity._cumulative_total = Decimal("25.5")

        # Test the _is_new_update method directly with same timestamp
        result = entity._is_new_update(Decimal("30.0"), 1234567890)  # Same timestamp

        # Should not be a new update
        assert result is False
        assert entity._cumulative_total == Decimal("25.5")  # Should not change

    def test_process_incremental_update_duplicate_value(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test _process_incremental_update with duplicate value."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Set initial values
        entity._last_raw_value = Decimal("25.5")
        entity._cumulative_total = Decimal("25.5")

        # Test the _is_new_update method directly with same value
        with patch("time.time", return_value=1234567.0):
            result = entity._is_new_update(Decimal("25.5"), None)

        # Should not be a new update
        assert result is False
        assert entity._cumulative_total == Decimal("25.5")  # Should not change

    def test_native_value_incremental_mode(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test native_value in incremental mode."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Set cumulative total
        entity._cumulative_total = Decimal("1500.75")

        value = entity.native_value
        assert value == 1500.75  # Should be converted to float

    def test_native_value_cumulative_mode(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_cumulative,
        mock_manager,
    ):
        """Test native_value in cumulative mode."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_cumulative,
        )

        # Mock the parent class's native_value property to ensure line 1912 is covered
        with patch.object(
            entity.__class__.__bases__[0],  # TuyaSensorEntity
            "native_value",
            new_callable=PropertyMock,
            return_value="2000.0",
        ):
            value = entity.native_value
            assert value == "2000.0"

    def test_extra_state_attributes_comprehensive(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_config_entry_with_cumulative,
        mock_manager,
    ):
        """Test extra_state_attributes comprehensively."""
        # Test incremental mode with all values
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )
        entity._cumulative_total = Decimal("1500.75")
        entity._last_update_time = 1234567890
        entity._last_raw_value = Decimal("25.5")

        attrs = entity.extra_state_attributes
        assert attrs["energy_report_mode"] == "incremental"
        assert attrs["cumulative_total"] == "1500.75"
        assert attrs["last_update_time"] == 1234567890
        assert attrs["last_raw_value"] == "25.5"

        # Test incremental mode with None values
        entity._last_update_time = None
        entity._last_raw_value = None
        attrs = entity.extra_state_attributes
        assert attrs["energy_report_mode"] == "incremental"
        assert attrs["cumulative_total"] == "1500.75"
        assert "last_update_time" not in attrs
        assert "last_raw_value" not in attrs

        # Test cumulative mode
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_cumulative,
        )
        attrs = entity.extra_state_attributes
        assert attrs["energy_report_mode"] == "cumulative"

        # Test non-energy sensor
        non_energy_description = TuyaSensorEntityDescription(
            key="cur_current",
            translation_key="current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
        )
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            non_energy_description,
            mock_config_entry_with_incremental,
        )
        attrs = entity.extra_state_attributes
        assert "energy_report_mode" not in attrs
        assert "cumulative_total" not in attrs

    def test_is_new_update_comprehensive(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test _is_new_update method comprehensively."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Test with newer timestamp
        entity._last_update_time = 1000
        result = entity._is_new_update(Decimal("25.5"), 2000)
        assert result is True
        assert entity._last_update_time == 2000
        assert entity._last_raw_value == Decimal("25.5")

        # Test with older timestamp
        result = entity._is_new_update(Decimal("30.0"), 1000)
        assert result is False
        assert entity._last_update_time == 2000  # Should not change

        # Test with no timestamp and different value
        entity._last_raw_value = Decimal("20.0")
        with patch("time.time", return_value=1234567.0):
            result = entity._is_new_update(Decimal("25.5"), None)
        assert result is True
        assert entity._last_raw_value == Decimal("25.5")
        assert entity._last_update_time == 1234567000

        # Test with no timestamp and duplicate value
        with patch("time.time", return_value=1234568.0):
            result = entity._is_new_update(Decimal("25.5"), None)
        assert result is False
        assert entity._last_raw_value == Decimal("25.5")  # Should not change

        # Test with no timestamp and no previous value
        entity._last_raw_value = None
        entity._last_update_time = None
        with patch("time.time", return_value=1234569.0):
            result = entity._is_new_update(Decimal("30.0"), None)
        assert result is True
        assert entity._last_raw_value == Decimal("30.0")
        assert entity._last_update_time == 1234569000

    @patch("homeassistant.components.tuya.sensor.TuyaSensorEntity.async_added_to_hass")
    async def test_restore_state_invalid_cases(
        self,
        mock_super,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
        hass: HomeAssistant,
    ):
        """Test restore state with invalid states and attributes."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Test with unknown state
        mock_state = MagicMock()
        mock_state.state = "unknown"
        mock_state.attributes = {}
        with patch.object(entity, "async_get_last_state", return_value=mock_state):
            await entity.async_added_to_hass()
        mock_super.assert_called_once()
        assert entity._cumulative_total == Decimal(0)
        assert entity._last_update_time is None
        assert entity._last_raw_value is None

        # Reset for next test
        mock_super.reset_mock()

        # Test with unavailable state
        mock_state.state = "unavailable"
        with patch.object(entity, "async_get_last_state", return_value=mock_state):
            await entity.async_added_to_hass()
        mock_super.assert_called_once()
        assert entity._cumulative_total == Decimal(0)
        assert entity._last_update_time is None
        assert entity._last_raw_value is None

        # Reset for next test
        mock_super.reset_mock()

        # Test with no attributes
        mock_state.state = "1000.0"
        mock_state.attributes = None
        with patch.object(entity, "async_get_last_state", return_value=mock_state):
            await entity.async_added_to_hass()
        mock_super.assert_called_once()
        assert entity._cumulative_total == Decimal(0)
        assert entity._last_update_time is None
        assert entity._last_raw_value is None

    def test_timestamp_handling_edge_cases(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test edge cases in timestamp handling."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Test edge case: very large timestamp
        large_timestamp = 9999999999999
        result = entity._is_new_update(Decimal("10.0"), large_timestamp)
        assert result is True
        assert entity._last_update_time == large_timestamp

        # Test edge case: zero timestamp - this should be considered newer than None
        entity._last_update_time = None  # Reset for next test
        entity._last_raw_value = None
        result = entity._is_new_update(Decimal("20.0"), 0)
        assert result is True
        assert entity._last_update_time == 0

        # Test edge case: negative timestamp - this should be considered newer than None
        # but since we already set _last_update_time to 0, it should be False
        result = entity._is_new_update(Decimal("30.0"), -1000)
        assert result is False  # Should not be considered new since 0 > -1000
        assert entity._last_update_time == 0  # Should remain unchanged

    def test_process_incremental_update_valid_cases(
        self,
        mock_energy_device,
        mock_energy_description,
        mock_config_entry_with_incremental,
        mock_manager,
    ):
        """Test _process_incremental_update with valid values."""
        entity = TuyaEnergySensorEntity(
            mock_energy_device,
            mock_manager,
            mock_energy_description,
            mock_config_entry_with_incremental,
        )

        # Test with valid value and _is_new_update returns True
        with (
            patch.object(
                entity.__class__.__bases__[0],
                "native_value",
                new_callable=PropertyMock,
                return_value="10.5",
            ),
            patch.object(entity, "_is_new_update", return_value=True),
        ):
            entity._process_incremental_update(1234567890)
        assert entity._cumulative_total == Decimal("10.5")  # Should accumulate

        # Test with valid value but _is_new_update returns False
        with (
            patch.object(
                entity.__class__.__bases__[0],
                "native_value",
                new_callable=PropertyMock,
                return_value="15.0",
            ),
            patch.object(entity, "_is_new_update", return_value=False),
        ):
            entity._process_incremental_update(1234567890)
        assert entity._cumulative_total == Decimal("10.5")  # Should not change
