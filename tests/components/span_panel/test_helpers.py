"""Tests for helper functions in the Span Panel integration."""

# pylint: disable=reimported

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.span_panel.const import (
    USE_CIRCUIT_NUMBERS,
    USE_DEVICE_PREFIX,
)
from homeassistant.components.span_panel.helpers import (
    async_create_span_notification,
    construct_120v_synthetic_entity_id,
    construct_240v_synthetic_entity_id,
    construct_circuit_identifier_from_tabs,
    construct_multi_circuit_entity_id,
    construct_panel_entity_id,
    construct_panel_synthetic_entity_id,
    construct_unmapped_circuit_id,
    construct_unmapped_entity_id,
    detect_capabilities,
    get_api_description_key_from_suffix,
    get_suffix_from_sensor_key,
    get_unmapped_circuit_entity_id,
    get_user_friendly_suffix,
    is_panel_level_sensor_key,
)
from homeassistant.util import slugify

from .factories import (
    SpanBatterySnapshotFactory,
    SpanCircuitSnapshotFactory,
    SpanEvseSnapshotFactory,
    SpanPanelSnapshotFactory,
)


def construct_synthetic_friendly_name(
    circuit_numbers: list[int],
    suffix_description: str,
    user_friendly_name: str | None = None,
) -> str:
    """Construct friendly display name for synthetic sensors (test helper).

    Args:
        circuit_numbers: List of circuit numbers (e.g., [30, 32] for solar inverter)
        suffix_description: Human-readable suffix (e.g., "Instant Power", "Energy Produced")
        user_friendly_name: Optional user-provided name (e.g., "Solar Production")

    Returns:
        Friendly name for display in Home Assistant

    """
    if user_friendly_name:
        # User provided a custom name - use it with the suffix
        return f"{user_friendly_name} {suffix_description}"

    # Fallback to circuit-based name
    valid_circuits = [str(num) for num in circuit_numbers if num > 0]
    if len(valid_circuits) > 1:
        circuit_spec = "-".join(valid_circuits)
        return f"Circuit {circuit_spec} {suffix_description}"
    if len(valid_circuits) == 1:
        return f"Circuit {valid_circuits[0]} {suffix_description}"
    return f"Unknown Circuit {suffix_description}"


class TestHelperFunctions:
    """Test the helper functions."""

    def test_slugify_name_for_entity_id(self):
        """Test name sanitization for entity IDs using HA's slugify."""
        assert slugify("Kitchen Outlets") == "kitchen_outlets"
        assert slugify("Main-Panel") == "main_panel"
        assert slugify("Test Name") == "test_name"
        assert slugify("UPPER CASE") == "upper_case"

    def test_get_user_friendly_suffix(self):
        """Test suffix mapping conversion."""
        assert get_user_friendly_suffix("instantPowerW") == "power"
        assert get_user_friendly_suffix("producedEnergyWh") == "energy_produced"
        assert get_user_friendly_suffix("circuit_priority") == "priority"
        assert get_user_friendly_suffix("unknown_field") == "unknown_field"

    def test_get_api_description_key_from_suffix(self):
        """Test reverse suffix lookup across circuit and panel sensors."""
        assert get_api_description_key_from_suffix("power") == "instantPowerW"
        assert (
            get_api_description_key_from_suffix("energy_produced") == "producedEnergyWh"
        )
        assert (
            get_api_description_key_from_suffix("current_power") == "instantGridPowerW"
        )
        assert get_api_description_key_from_suffix("missing_suffix") is None

    def test_get_suffix_from_sensor_key(self):
        """Test suffix extraction from panel and synthetic sensor keys."""
        assert get_suffix_from_sensor_key("span_abc123_solar_inverter_power") == "power"
        assert (
            get_suffix_from_sensor_key("span_abc123_house_total_energy_produced")
            == "energy_produced"
        )
        assert get_suffix_from_sensor_key("plain_sensor_name") == "name"

    def test_is_panel_level_sensor_key(self):
        """Test classification of panel-level and circuit-level sensor keys."""
        assert is_panel_level_sensor_key("span_span12345678_current_power") is True
        assert (
            is_panel_level_sensor_key(
                "span_span12345678_12ce227695cd44338864b0ef2ec4168b_instantPowerW"
            )
            is False
        )
        assert is_panel_level_sensor_key("invalid_format") is False

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_multi_circuit_entity_id_config_entry_none(self, mock_registry):
        """Test construct_multi_circuit_entity_id works with valid coordinator (None config_entry should be caught at coordinator level)."""
        mock_registry.return_value = None

        coordinator = MagicMock()
        coordinator.config_entry.options = {}
        coordinator.config_entry.title = "SPAN Panel"
        span_panel = MagicMock()

        # This should work fine - the coordinator should validate config_entry at construction time
        result = construct_multi_circuit_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            circuit_numbers=[3032],
            friendly_name="Solar Inverter",
        )
        # With empty options, should use legacy naming (no device prefix)
        assert result == "sensor.solar_inverter_power"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_multi_circuit_entity_id_empty_options(self, mock_registry):
        """Test construct_multi_circuit_entity_id with stable naming (synthetic sensors are always stable)."""
        mock_registry.return_value = None

        coordinator = MagicMock()
        coordinator.config_entry.options = {}
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.config_entry.data = {"device_name": "SPAN Panel"}
        span_panel = MagicMock()

        # Test with friendly name - legacy installation should not use device prefix
        result = construct_multi_circuit_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            circuit_numbers=[30, 32],
            friendly_name="Solar Production Power",
        )
        assert result == "sensor.solar_production_power"

        # Test with default friendly name - legacy installation should not use device prefix
        result = construct_multi_circuit_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            circuit_numbers=[30, 32],
            friendly_name="Solar Inverter",
        )
        assert result == "sensor.solar_inverter_power"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_multi_circuit_entity_id_no_device_name(self, mock_registry):
        """Test construct_multi_circuit_entity_id with no device name - should return None."""
        mock_registry.return_value = None

        coordinator = MagicMock()
        coordinator.config_entry.options = {USE_CIRCUIT_NUMBERS: True}
        coordinator.config_entry.title = None
        coordinator.config_entry.data = {"device_name": None}
        span_panel = MagicMock()

        # Multi-circuit sensors should return None if no device name available
        result = construct_multi_circuit_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            circuit_numbers=[30, 32],
            friendly_name="Solar Inverter",
        )
        assert result is None

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_multi_circuit_entity_id_circuit_numbers_pattern(
        self, mock_registry
    ):
        """Test construct_multi_circuit_entity_id with circuit numbers pattern."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(return_value=None)

        coordinator = MagicMock()
        coordinator.config_entry.options = {
            USE_CIRCUIT_NUMBERS: True,
            USE_DEVICE_PREFIX: True,
        }
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.config_entry.data = {"device_name": "SPAN Panel"}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test with multiple circuit numbers (solar inverter case)
        result = construct_multi_circuit_entity_id(
            coordinator, span_panel, "sensor", "power", circuit_numbers=[30, 32]
        )
        assert result == "sensor.span_panel_circuit_30_32_power"

        # Test with single circuit number
        result = construct_multi_circuit_entity_id(
            coordinator, span_panel, "sensor", "power", circuit_numbers=[15]
        )
        assert result == "sensor.span_panel_circuit_15_power"

        # Test with different suffix
        result = construct_multi_circuit_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "energy_produced",
            circuit_numbers=[30, 32],
        )
        assert result == "sensor.span_panel_circuit_30_32_energy_produced"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_multi_circuit_entity_id_friendly_names_pattern(
        self, mock_registry
    ):
        """Test construct_multi_circuit_entity_id with friendly names pattern."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(return_value=None)

        coordinator = MagicMock()
        coordinator.config_entry.options = {
            USE_CIRCUIT_NUMBERS: False,
            USE_DEVICE_PREFIX: True,
        }
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.config_entry.data = {"device_name": "SPAN Panel"}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test with friendly name (should ignore circuit_numbers when USE_CIRCUIT_NUMBERS is False)
        result = construct_multi_circuit_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            circuit_numbers=[30, 32],
            friendly_name="Solar Inverter",
        )
        assert result == "sensor.span_panel_solar_inverter_power"

        # Test without friendly name (should return None when not using circuit numbers)
        result = construct_multi_circuit_entity_id(
            coordinator, span_panel, "sensor", "power", circuit_numbers=[30, 32]
        )
        assert result is None

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_multi_circuit_entity_id_circuit_numbers_no_device_prefix(
        self, mock_registry
    ):
        """Test construct_multi_circuit_entity_id with circuit numbers but no device prefix."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(return_value=None)

        coordinator = MagicMock()
        coordinator.config_entry.options = {
            USE_CIRCUIT_NUMBERS: True,
            USE_DEVICE_PREFIX: False,
        }
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.config_entry.data = {"device_name": "SPAN Panel"}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test with circuit numbers but no device prefix (should still work for multi-circuit sensors)
        result = construct_multi_circuit_entity_id(
            coordinator, span_panel, "sensor", "power", circuit_numbers=[30, 32]
        )
        assert result == "sensor.circuit_30_32_power"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_multi_circuit_entity_id_empty_circuit_numbers(
        self, mock_registry
    ):
        """Test construct_multi_circuit_entity_id with empty circuit numbers."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(return_value=None)

        coordinator = MagicMock()
        coordinator.config_entry.options = {
            USE_CIRCUIT_NUMBERS: True,
            USE_DEVICE_PREFIX: True,
        }
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.config_entry.data = {"device_name": "SPAN Panel"}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test with empty circuit numbers (should raise ValueError)
        with pytest.raises(
            ValueError,
            match="Circuit-based naming is enabled but no valid circuit numbers provided",
        ):
            construct_multi_circuit_entity_id(
                coordinator, span_panel, "sensor", "power", circuit_numbers=[]
            )

        # Test with None circuit numbers (should raise ValueError)
        with pytest.raises(
            ValueError,
            match="Circuit-based naming is enabled but no valid circuit numbers provided",
        ):
            construct_multi_circuit_entity_id(
                coordinator, span_panel, "sensor", "power", circuit_numbers=None
            )

        # Test with invalid circuit numbers (should raise ValueError)
        with pytest.raises(
            ValueError,
            match="Circuit-based naming is enabled but no valid circuit numbers provided",
        ):
            construct_multi_circuit_entity_id(
                coordinator, span_panel, "sensor", "power", circuit_numbers=[0, -1]
            )

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_multi_circuit_entity_id_legacy_compatibility(
        self, mock_registry
    ):
        """Test construct_multi_circuit_entity_id maintains legacy compatibility."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(return_value=None)

        coordinator = MagicMock()
        coordinator.config_entry.options = {}  # Legacy installation
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.config_entry.data = {"device_name": "SPAN Panel"}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test legacy compatibility - should work with circuit_numbers parameter
        result = construct_multi_circuit_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            circuit_numbers=[30, 32],
            friendly_name="Solar Inverter",
        )
        assert result == "sensor.solar_inverter_power"

        # Test legacy compatibility - should work with circuit_numbers but ignore them in legacy mode
        result = construct_multi_circuit_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            circuit_numbers=[30, 32],
            friendly_name="Solar Inverter",
        )
        assert result == "sensor.solar_inverter_power"

    def test_construct_synthetic_friendly_name_with_user_name(self):
        """Test construct_synthetic_friendly_name with user-provided name."""
        result = construct_synthetic_friendly_name(
            [30, 32], "Instant Power", "Solar Production"
        )
        assert result == "Solar Production Instant Power"

    def test_construct_synthetic_friendly_name_multiple_circuits(self):
        """Test construct_synthetic_friendly_name with multiple circuits."""
        result = construct_synthetic_friendly_name([30, 32], "Instant Power")
        assert result == "Circuit 30-32 Instant Power"

    def test_construct_synthetic_friendly_name_single_circuit(self):
        """Test construct_synthetic_friendly_name with single circuit."""
        result = construct_synthetic_friendly_name([30], "Instant Power")
        assert result == "Circuit 30 Instant Power"

    def test_construct_synthetic_friendly_name_no_valid_circuits(self):
        """Test construct_synthetic_friendly_name with no valid circuits."""
        result = construct_synthetic_friendly_name([0, -1], "Instant Power")
        assert result == "Unknown Circuit Instant Power"

    def test_construct_synthetic_friendly_name_empty_circuits(self):
        """Test construct_synthetic_friendly_name with empty circuit list."""
        result = construct_synthetic_friendly_name([], "Instant Power")
        assert result == "Unknown Circuit Instant Power"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_panel_entity_id_with_device_prefix(self, mock_registry):
        """Test construct_panel_entity_id with device prefix enabled."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(return_value=None)

        coordinator = MagicMock()
        coordinator.config_entry.options = {USE_DEVICE_PREFIX: True}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test with device prefix enabled
        result = construct_panel_entity_id(
            coordinator,
            span_panel,
            "binary_sensor",
            "wwanlink",
            "SPAN Panel",
            unique_id="test_unique_id",
            use_device_prefix=True,
        )
        assert result == "binary_sensor.span_panel_wwanlink"

        # Test with device prefix disabled
        result = construct_panel_entity_id(
            coordinator,
            span_panel,
            "binary_sensor",
            "wwanlink",
            "SPAN Panel",
            unique_id="test_unique_id",
            use_device_prefix=False,
        )
        assert result == "binary_sensor.wwanlink"

        # Test with device prefix from config (True)
        result = construct_panel_entity_id(
            coordinator,
            span_panel,
            "binary_sensor",
            "wwanlink",
            "SPAN Panel",
            unique_id="test_unique_id",
            use_device_prefix=None,  # Should use config
        )
        assert result == "binary_sensor.span_panel_wwanlink"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_panel_entity_id_without_device_prefix(self, mock_registry):
        """Test construct_panel_entity_id with device prefix disabled."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(return_value=None)

        coordinator = MagicMock()
        coordinator.config_entry.options = {USE_DEVICE_PREFIX: False}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test with device prefix from config (False)
        result = construct_panel_entity_id(
            coordinator,
            span_panel,
            "binary_sensor",
            "wwanlink",
            "SPAN Panel",
            unique_id="test_unique_id",
            use_device_prefix=None,  # Should use config
        )
        assert result == "binary_sensor.wwanlink"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_panel_entity_id_no_device_name_returns_none(self, mock_registry):
        """Test construct_panel_entity_id returns None when device name is missing."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(return_value=None)

        coordinator = MagicMock()
        coordinator.config_entry.options = {USE_DEVICE_PREFIX: True}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        result = construct_panel_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "current_power",
            "",
            unique_id=None,
        )

        assert result is None

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_panel_entity_id_registry_lookup(self, mock_registry):
        """Test construct_panel_entity_id with existing entity in registry."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(
            return_value="binary_sensor.existing_entity"
        )

        coordinator = MagicMock()
        coordinator.config_entry.options = {USE_DEVICE_PREFIX: True}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test with existing entity in registry
        result = construct_panel_entity_id(
            coordinator,
            span_panel,
            "binary_sensor",
            "wwanlink",
            "SPAN Panel",
            unique_id="test_unique_id",
            use_device_prefix=True,
        )
        assert result == "binary_sensor.existing_entity"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_panel_entity_id_different_platforms(self, mock_registry):
        """Test construct_panel_entity_id with different platforms."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(return_value=None)

        coordinator = MagicMock()
        coordinator.config_entry.options = {USE_DEVICE_PREFIX: True}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test with binary_sensor platform
        result = construct_panel_entity_id(
            coordinator,
            span_panel,
            "binary_sensor",
            "wwanlink",
            "SPAN Panel",
            use_device_prefix=True,
        )
        assert result == "binary_sensor.span_panel_wwanlink"

        # Test with sensor platform
        result = construct_panel_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "current_power",
            "SPAN Panel",
            use_device_prefix=True,
        )
        assert result == "sensor.span_panel_current_power"

        # Test with switch platform
        result = construct_panel_entity_id(
            coordinator,
            span_panel,
            "switch",
            "test_switch",
            "SPAN Panel",
            use_device_prefix=True,
        )
        assert result == "switch.span_panel_test_switch"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_binary_sensor_entity_id_construction_simulation(self, mock_registry):
        """Test that simulates exactly what the binary sensor does when creating entity IDs."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(return_value=None)

        # Simulate the binary sensor setup
        coordinator = MagicMock()
        coordinator.config_entry.options = {USE_DEVICE_PREFIX: True}
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.config_entry.data = {"device_name": "SPAN Panel"}
        coordinator.hass = MagicMock()

        span_panel = MagicMock()
        span_panel.status.serial_number = "TEST123456"

        # Simulate the wwanLink binary sensor
        device_name = coordinator.config_entry.data.get(
            "device_name", coordinator.config_entry.title
        )
        use_device_prefix = coordinator.config_entry.options.get(
            USE_DEVICE_PREFIX, False
        )

        entity_id = construct_panel_entity_id(
            coordinator,
            span_panel,
            "binary_sensor",
            "wwanlink",  # description.key.lower()
            device_name,
            "test_unique_id",  # self._attr_unique_id
            use_device_prefix,
        )

        # This should match what we expect in the logs
        assert entity_id == "binary_sensor.span_panel_wwanlink"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_sensor_entity_id_construction_simulation(self, mock_registry):
        """Test that simulates exactly what the sensor does when creating entity IDs."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(return_value=None)

        # Simulate the sensor setup
        coordinator = MagicMock()
        coordinator.config_entry.options = {USE_DEVICE_PREFIX: True}
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.config_entry.data = {"device_name": "SPAN Panel"}
        coordinator.hass = MagicMock()

        span_panel = MagicMock()
        span_panel.status.serial_number = "TEST123456"

        # Simulate the dsm_state sensor
        device_name = "SPAN Panel"
        use_device_prefix = True

        entity_id = construct_panel_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "dsm_state",  # suffix
            device_name,
            "test_unique_id",  # unique_id
            use_device_prefix,
        )

        # This should match what we expect in the logs
        assert entity_id == "sensor.span_panel_dsm_state"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_panel_synthetic_entity_id(self, mock_registry):
        """Test construct_panel_synthetic_entity_id for panel-level synthetic sensors."""
        mock_registry.return_value = MagicMock()
        # Mock the registry to return an existing entity ID for the unique_id
        mock_registry.return_value.async_get_entity_id = MagicMock(
            return_value="sensor.existing_entity"
        )

        coordinator = MagicMock()
        coordinator.config_entry.options = {USE_DEVICE_PREFIX: True}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test with device prefix enabled and existing unique_id
        result = construct_panel_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "current_power",
            "SPAN Panel",
            unique_id="test_unique_id",
        )
        assert result == "sensor.existing_entity"

        # Test with device prefix enabled and no unique_id (should construct new entity_id)
        result = construct_panel_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "current_power",
            "SPAN Panel",
            unique_id=None,
        )
        assert result == "sensor.span_panel_current_power"

        # Test with device prefix disabled and no unique_id
        coordinator.config_entry.options = {USE_DEVICE_PREFIX: False}
        result = construct_panel_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "current_power",
            "SPAN Panel",
            unique_id=None,
        )
        assert result == "sensor.current_power"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_panel_synthetic_entity_id_missing_registry_entry_raises(
        self, mock_registry
    ):
        """Test construct_panel_synthetic_entity_id raises on missing registry entry."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(return_value=None)

        coordinator = MagicMock()
        coordinator.config_entry.options = {USE_DEVICE_PREFIX: True}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        with pytest.raises(
            ValueError, match="Expected unique_id 'test_unique_id' not found"
        ):
            construct_panel_synthetic_entity_id(
                coordinator,
                span_panel,
                "sensor",
                "current_power",
                "SPAN Panel",
                unique_id="test_unique_id",
            )

    def test_construct_panel_synthetic_entity_id_no_device_name_returns_none(self):
        """Test synthetic panel IDs return None when the panel name is unavailable."""
        coordinator = MagicMock()
        coordinator.config_entry.options = {USE_DEVICE_PREFIX: True}
        span_panel = MagicMock()

        result = construct_panel_synthetic_entity_id(
            coordinator, span_panel, "sensor", "current_power", "", unique_id=None
        )

        assert result is None

    def test_construct_240v_synthetic_entity_id_circuit_numbers(self):
        """Test construct_240v_synthetic_entity_id with circuit numbers pattern."""
        coordinator = MagicMock()
        coordinator.config_entry.options = {
            USE_CIRCUIT_NUMBERS: True,
            USE_DEVICE_PREFIX: True,
        }
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.config_entry.data = {"device_name": "SPAN Panel"}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test 240V solar sensor with circuit numbers
        result = construct_240v_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            friendly_name="Solar",
            tab1=30,
            tab2=32,
        )
        assert result == "sensor.span_panel_circuit_30_32_power"

        # Test with different suffix
        result = construct_240v_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "energy_produced",
            friendly_name="Solar",
            tab1=30,
            tab2=32,
        )
        assert result == "sensor.span_panel_circuit_30_32_energy_produced"

    def test_construct_240v_synthetic_entity_id_friendly_names(self):
        """Test construct_240v_synthetic_entity_id with friendly names pattern."""
        coordinator = MagicMock()
        coordinator.config_entry.options = {
            USE_CIRCUIT_NUMBERS: False,
            USE_DEVICE_PREFIX: True,
        }
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.config_entry.data = {"device_name": "SPAN Panel"}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test 240V solar sensor with friendly names
        result = construct_240v_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            friendly_name="Solar",
            tab1=30,
            tab2=32,
        )
        assert result == "sensor.span_panel_solar_power"

        # Test 240V named circuit with friendly name
        result = construct_240v_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            friendly_name="Air Conditioner",
            tab1=15,
            tab2=17,
        )
        assert result == "sensor.span_panel_air_conditioner_power"

    def test_construct_120v_synthetic_entity_id_circuit_numbers(self):
        """Test construct_120v_synthetic_entity_id with circuit numbers pattern."""
        coordinator = MagicMock()
        coordinator.config_entry.options = {
            USE_CIRCUIT_NUMBERS: True,
            USE_DEVICE_PREFIX: True,
        }
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.config_entry.data = {"device_name": "SPAN Panel"}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test 120V solar sensor with circuit numbers
        result = construct_120v_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            friendly_name="Solar",
            tab=30,
        )
        assert result == "sensor.span_panel_circuit_30_power"

        # Test with different suffix
        result = construct_120v_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "energy_consumed",
            friendly_name="Solar",
            tab=30,
        )
        assert result == "sensor.span_panel_circuit_30_energy_consumed"

    def test_construct_120v_synthetic_entity_id_friendly_names(self):
        """Test construct_120v_synthetic_entity_id with friendly names pattern."""
        coordinator = MagicMock()
        coordinator.config_entry.options = {
            USE_CIRCUIT_NUMBERS: False,
            USE_DEVICE_PREFIX: True,
        }
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.config_entry.data = {"device_name": "SPAN Panel"}
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test 120V solar sensor with friendly names
        result = construct_120v_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            friendly_name="Solar",
            tab=30,
        )
        assert result == "sensor.span_panel_solar_power"

        # Test 120V named circuit with friendly name
        result = construct_120v_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            friendly_name="Kitchen Outlets",
            tab=16,
        )
        assert result == "sensor.span_panel_kitchen_outlets_power"

    def test_construct_synthetic_entity_id_no_device_prefix(self):
        """Test synthetic entity ID construction without device prefix."""
        coordinator = MagicMock()
        coordinator.config_entry.options = {
            USE_CIRCUIT_NUMBERS: True,
            USE_DEVICE_PREFIX: False,
        }
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test 240V without device prefix
        result = construct_240v_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            friendly_name="Solar",
            tab1=30,
            tab2=32,
        )
        assert result == "sensor.circuit_30_32_power"

        # Test 120V without device prefix
        result = construct_120v_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            friendly_name="Solar",
            tab=30,
        )
        assert result == "sensor.circuit_30_power"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_construct_synthetic_entity_id_registry_lookup(self, mock_registry):
        """Test synthetic entity ID construction with existing entity in registry."""
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.async_get_entity_id = MagicMock(
            return_value="sensor.existing_solar_current_power"
        )

        coordinator = MagicMock()
        coordinator.config_entry.options = {
            USE_CIRCUIT_NUMBERS: True,
            USE_DEVICE_PREFIX: True,
        }
        coordinator.config_entry.title = "SPAN Panel"
        coordinator.hass = MagicMock()
        span_panel = MagicMock()

        # Test registry lookup with existing entity
        result = construct_240v_synthetic_entity_id(
            coordinator,
            span_panel,
            "sensor",
            "power",
            friendly_name="Solar",
            tab1=30,
            tab2=32,
            unique_id="test_unique_id",
        )
        assert result == "sensor.existing_solar_current_power"

    def test_construct_unmapped_entity_helpers(self):
        """Test helper functions for unmapped circuits."""
        snapshot = SpanPanelSnapshotFactory.create(
            circuits={
                "unmapped_tab_7": SpanCircuitSnapshotFactory.create(
                    circuit_id="unmapped_tab_7"
                )
            }
        )

        assert construct_unmapped_circuit_id(7) == "unmapped_tab_7"
        assert (
            construct_unmapped_entity_id(
                snapshot, "unmapped_tab_7", "power", "SPAN Panel"
            )
            == "sensor.span_panel_unmapped_tab_7_power"
        )
        assert (
            get_unmapped_circuit_entity_id(snapshot, 7, "power", "SPAN Panel")
            == "sensor.span_panel_unmapped_tab_7_power"
        )
        assert (
            get_unmapped_circuit_entity_id(snapshot, 99, "power", "SPAN Panel") is None
        )

    def test_construct_circuit_identifier_from_tabs(self):
        """Test fallback circuit naming from tabs."""
        assert construct_circuit_identifier_from_tabs([5, 6], "c1") == "Circuit 5 6"
        assert construct_circuit_identifier_from_tabs([7], "c1") == "Circuit 7"
        assert (
            construct_circuit_identifier_from_tabs([], "fallback") == "Circuit fallback"
        )

    @patch("homeassistant.components.span_panel.helpers.async_create")
    @pytest.mark.asyncio
    async def test_async_create_span_notification_logs_and_forwards(self, mock_create):
        """Test notification helper forwarding."""
        hass = MagicMock()

        await async_create_span_notification(
            hass,
            "Panel connection lost",
            "SPAN Alert",
            "notif-1",
            level="error",
        )

        mock_create.assert_called_once_with(
            hass,
            message="Panel connection lost",
            title="SPAN Alert",
            notification_id="notif-1",
        )

    def test_detect_capabilities_helper(self):
        """Test capability detection from a populated snapshot."""
        snapshot = SpanPanelSnapshotFactory.create(
            battery=SpanBatterySnapshotFactory.create(soe_percentage=88.0),
            power_flow_pv=1200.0,
            power_flow_site=3000.0,
            evse={"evse-0": SpanEvseSnapshotFactory.create()},
        )

        assert detect_capabilities(snapshot) == frozenset(
            {"bess", "evse", "power_flows", "pv"}
        )
