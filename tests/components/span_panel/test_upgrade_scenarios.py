"""Test upgrade scenarios to ensure existing installations are preserved."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.span_panel.config_flow import OptionsFlowHandler
from homeassistant.components.span_panel.config_flow_options import (
    get_current_naming_pattern,
)
from homeassistant.components.span_panel.const import (
    USE_CIRCUIT_NUMBERS,
    USE_DEVICE_PREFIX,
    EntityNamingPattern,
)
from homeassistant.components.span_panel.helpers import (
    construct_multi_circuit_entity_id,
    construct_single_circuit_entity_id,
)

from .factories import SpanCircuitSnapshotFactory, SpanPanelSnapshotFactory


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.async_block_till_done = AsyncMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_reload = AsyncMock()
    hass.config_entries.async_get_entry = MagicMock()
    hass.async_create_task = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""

    class MockConfigEntry:
        def __init__(self) -> None:
            self.entry_id = "test_entry_id"
            self.options = {}

    return MockConfigEntry()


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.config_entry = None  # Will be set in tests
    coordinator.hass = MagicMock()  # Mock hass for entity registry access
    return coordinator


@pytest.fixture
def mock_span_panel():
    """Create a mock span panel."""
    panel = MagicMock()
    panel.status.serial_number = "TEST123"
    return panel


class TestUpgradeScenarios:
    """Test upgrade scenarios for different installation types."""

    def test_legacy_installation_preserved_on_upgrade(self, mock_config_entry):
        """Test that legacy installations (pre-1.0.4) are preserved during upgrades."""
        mock_config_entry.options = {
            USE_DEVICE_PREFIX: False,
            USE_CIRCUIT_NUMBERS: False,
        }
        assert (
            get_current_naming_pattern(mock_config_entry)
            == EntityNamingPattern.LEGACY_NAMES.value
        )

    def test_post_104_friendly_names_preserved_on_upgrade(self, mock_config_entry):
        """Test that post-1.0.4 friendly names installations are preserved during upgrades."""
        mock_config_entry.options = {
            USE_DEVICE_PREFIX: True,
            USE_CIRCUIT_NUMBERS: False,
        }
        assert (
            get_current_naming_pattern(mock_config_entry)
            == EntityNamingPattern.FRIENDLY_NAMES.value
        )

    def test_modern_circuit_numbers_preserved_on_upgrade(self, mock_config_entry):
        """Test that modern circuit numbers installations are preserved during upgrades."""
        mock_config_entry.options = {
            USE_DEVICE_PREFIX: True,
            USE_CIRCUIT_NUMBERS: True,
        }
        assert (
            get_current_naming_pattern(mock_config_entry)
            == EntityNamingPattern.CIRCUIT_NUMBERS.value
        )

    def test_missing_options_default_to_new_installation_behavior(
        self, mock_config_entry
    ):
        """Test that missing options default to existing installation behavior (legacy)."""
        mock_config_entry.options = {}
        assert (
            get_current_naming_pattern(mock_config_entry)
            == EntityNamingPattern.LEGACY_NAMES.value
        )

    def test_partial_options_default_correctly(self, mock_config_entry):
        """Test that partial options still work correctly with defaults."""
        mock_config_entry.options = {
            USE_DEVICE_PREFIX: False,
        }
        assert (
            get_current_naming_pattern(mock_config_entry)
            == EntityNamingPattern.LEGACY_NAMES.value
        )

    def test_new_installation_gets_modern_defaults(self, mock_config_entry):
        """Test that new installations get modern defaults (circuit numbers)."""
        mock_config_entry.options = {
            USE_DEVICE_PREFIX: True,
            USE_CIRCUIT_NUMBERS: True,
        }
        assert (
            get_current_naming_pattern(mock_config_entry)
            == EntityNamingPattern.CIRCUIT_NUMBERS.value
        )


class TestEntityIdConstructionUpgradeScenarios:
    """Test entity ID construction preserves existing patterns during upgrades."""

    def _make_coordinator_and_snapshot(self, options, circuit_tabs=None):
        """Build a coordinator mock and snapshot with a single circuit."""
        circuit = SpanCircuitSnapshotFactory.create(
            circuit_id="15",
            name="Kitchen Outlets",
            tabs=circuit_tabs or [15],
        )
        snapshot = SpanPanelSnapshotFactory.create(circuits={"15": circuit})
        coordinator = MagicMock()
        coordinator.data = snapshot
        coordinator.config_entry = MagicMock()
        coordinator.config_entry.title = "Span Panel"
        coordinator.config_entry.data = {"device_name": "Span Panel"}
        coordinator.config_entry.options = options
        coordinator.hass = MagicMock()
        return coordinator, snapshot, circuit

    def test_legacy_entity_id_construction_preserved(self):
        """Test that legacy entity ID construction is preserved."""
        coordinator, snapshot, circuit = self._make_coordinator_and_snapshot(
            {USE_DEVICE_PREFIX: False, USE_CIRCUIT_NUMBERS: False}
        )
        entity_id = construct_single_circuit_entity_id(
            coordinator,
            snapshot,
            "sensor",
            "power",
            circuit,
        )
        assert entity_id == "sensor.kitchen_outlets_power"

    def test_post_104_friendly_names_entity_id_construction_preserved(self):
        """Test that post-1.0.4 friendly names entity ID construction is preserved."""
        coordinator, snapshot, circuit = self._make_coordinator_and_snapshot(
            {USE_DEVICE_PREFIX: True, USE_CIRCUIT_NUMBERS: False}
        )
        entity_id = construct_single_circuit_entity_id(
            coordinator,
            snapshot,
            "sensor",
            "power",
            circuit,
        )
        assert entity_id == "sensor.span_panel_kitchen_outlets_power"

    def test_modern_circuit_numbers_120v_entity_id_construction_preserved(self):
        """Test that modern circuit numbers entity ID for 120V is preserved."""
        coordinator, snapshot, circuit = self._make_coordinator_and_snapshot(
            {USE_DEVICE_PREFIX: True, USE_CIRCUIT_NUMBERS: True},
            circuit_tabs=[15],
        )
        entity_id = construct_single_circuit_entity_id(
            coordinator,
            snapshot,
            "sensor",
            "power",
            circuit,
        )
        assert entity_id == "sensor.span_panel_circuit_15_power"

    def test_modern_circuit_numbers_240v_entity_id_includes_both_tabs(self):
        """Test that 240V circuits include both tabs in entity ID."""
        coordinator, snapshot, circuit = self._make_coordinator_and_snapshot(
            {USE_DEVICE_PREFIX: True, USE_CIRCUIT_NUMBERS: True},
            circuit_tabs=[15, 17],
        )
        entity_id = construct_single_circuit_entity_id(
            coordinator,
            snapshot,
            "sensor",
            "power",
            circuit,
        )
        assert entity_id == "sensor.span_panel_circuit_15_17_power"


class TestSyntheticEntityUpgradeScenarios:
    """Test synthetic entity construction preserves existing patterns during upgrades."""

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_legacy_synthetic_entity_construction_preserved(
        self, mock_registry, mock_coordinator, mock_span_panel
    ):
        """Test that legacy synthetic entity construction is preserved."""
        mock_registry.return_value = None

        mock_config_entry = MagicMock()
        mock_config_entry.options = {
            USE_DEVICE_PREFIX: False,
            USE_CIRCUIT_NUMBERS: False,
        }
        mock_config_entry.title = "Span Panel"
        mock_config_entry.data = {"device_name": "Span Panel"}
        mock_coordinator.config_entry = mock_config_entry

        entity_id = construct_multi_circuit_entity_id(
            mock_coordinator,
            mock_span_panel,
            "sensor",
            "power",
            circuit_numbers=[30, 32],
            friendly_name="Solar Inverter",
        )
        assert entity_id == "sensor.solar_inverter_power"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_post_104_synthetic_entity_construction_preserved(
        self, mock_registry, mock_coordinator, mock_span_panel
    ):
        """Test that post-1.0.4 synthetic entity construction is preserved."""
        mock_registry.return_value = None

        mock_config_entry = MagicMock()
        mock_config_entry.options = {
            USE_DEVICE_PREFIX: True,
            USE_CIRCUIT_NUMBERS: False,
        }
        mock_config_entry.title = "Span Panel"
        mock_config_entry.data = {"device_name": "Span Panel"}
        mock_coordinator.config_entry = mock_config_entry

        entity_id = construct_multi_circuit_entity_id(
            mock_coordinator,
            mock_span_panel,
            "sensor",
            "power",
            circuit_numbers=[30, 32],
            friendly_name="Solar Inverter",
        )
        assert entity_id == "sensor.span_panel_solar_inverter_power"

    @patch("homeassistant.components.span_panel.helpers.er.async_get")
    def test_modern_synthetic_entity_construction_preserved(
        self, mock_registry, mock_coordinator, mock_span_panel
    ):
        """Test that modern synthetic entity construction is preserved."""
        mock_registry.return_value = None

        mock_config_entry = MagicMock()
        mock_config_entry.options = {
            USE_DEVICE_PREFIX: True,
            USE_CIRCUIT_NUMBERS: True,
        }
        mock_config_entry.title = "Span Panel"
        mock_config_entry.data = {"device_name": "Span Panel"}
        mock_coordinator.config_entry = mock_config_entry

        entity_id = construct_multi_circuit_entity_id(
            mock_coordinator,
            mock_span_panel,
            "sensor",
            "power",
            circuit_numbers=[30, 32],
            friendly_name="Solar Inverter",
        )
        assert entity_id == "sensor.span_panel_circuit_30_32_power"


class TestGeneralOptionsPreservesNamingFlags:
    """Test that general options flow preserves naming flags."""

    async def test_general_options_preserves_legacy_flags(
        self, mock_hass, mock_config_entry
    ):
        """Test that general options flow preserves legacy naming flags."""
        # Legacy installation flags
        mock_config_entry.options = {
            USE_DEVICE_PREFIX: False,
            USE_CIRCUIT_NUMBERS: False,
            "enable_solar_circuit": True,
            "leg1": 30,
            "leg2": 32,
        }

        with patch.object(OptionsFlowHandler, "__init__", return_value=None):
            flow = OptionsFlowHandler.__new__(OptionsFlowHandler)
            flow.hass = mock_hass

            # Simulate general options form submission (only changing solar settings)
            user_input = {
                "enable_solar_circuit": False,  # Changed
                "leg1": 30,  # Unchanged
                "leg2": 32,  # Unchanged
            }

            # Mock the config_entry property and async_step_general_options method
            with (
                patch.object(
                    OptionsFlowHandler,
                    "config_entry",
                    new_callable=lambda: mock_config_entry,
                ),
                patch.object(flow, "async_create_entry") as mock_create_entry,
            ):
                await flow.async_step_general_options(user_input)

                # Verify that naming flags were preserved
                mock_create_entry.assert_called_once()
                result_data = mock_create_entry.call_args[1]["data"]
                assert result_data.get(USE_DEVICE_PREFIX) is False  # Preserved
                assert result_data.get(USE_CIRCUIT_NUMBERS) is False  # Preserved

    async def test_general_options_preserves_modern_flags(
        self, mock_hass, mock_config_entry
    ):
        """Test that general options flow preserves modern naming flags."""
        # Modern installation flags
        mock_config_entry.options = {
            USE_DEVICE_PREFIX: True,
            USE_CIRCUIT_NUMBERS: True,
            "enable_solar_circuit": False,
            "leg1": 30,
            "leg2": 32,
        }

        with patch.object(OptionsFlowHandler, "__init__", return_value=None):
            flow = OptionsFlowHandler.__new__(OptionsFlowHandler)
            flow.hass = mock_hass

            # Simulate general options form submission (only changing solar settings)
            user_input = {
                "enable_solar_circuit": True,  # Changed
                "leg1": 28,  # Changed
                "leg2": 30,  # Changed
            }

            # Mock the config_entry property and async_step_general_options method
            with (
                patch.object(
                    OptionsFlowHandler,
                    "config_entry",
                    new_callable=lambda: mock_config_entry,
                ),
                patch.object(flow, "async_create_entry") as mock_create_entry,
            ):
                await flow.async_step_general_options(user_input)

                # Verify that naming flags were preserved
                mock_create_entry.assert_called_once()
                result_data = mock_create_entry.call_args[1]["data"]
                assert result_data.get(USE_DEVICE_PREFIX) is True  # Preserved
                assert result_data.get(USE_CIRCUIT_NUMBERS) is True  # Preserved

    async def test_general_options_handles_missing_flags_with_defaults(
        self, mock_hass, mock_config_entry
    ):
        """Test that general options flow handles missing flags with defaults."""
        # Installation with missing naming flags (edge case)
        mock_config_entry.options = {
            "enable_solar_circuit": True,
            "leg1": 30,
            "leg2": 32,
            # Missing USE_DEVICE_PREFIX and USE_CIRCUIT_NUMBERS
        }

        with patch.object(OptionsFlowHandler, "__init__", return_value=None):
            flow = OptionsFlowHandler.__new__(OptionsFlowHandler)
            flow.hass = mock_hass

            # Simulate general options form submission
            user_input = {
                "enable_solar_circuit": False,  # Changed
                "leg1": 30,
                "leg2": 32,
            }

            # Mock the config_entry property and async_step_general_options method
            with (
                patch.object(
                    OptionsFlowHandler,
                    "config_entry",
                    new_callable=lambda: mock_config_entry,
                ),
                patch.object(flow, "async_create_entry") as mock_create_entry,
            ):
                await flow.async_step_general_options(user_input)

                # Verify that missing flags get defaults (True for safety, prevents treating as legacy)
                mock_create_entry.assert_called_once()
                result_data = mock_create_entry.call_args[1]["data"]
                assert (
                    result_data.get(USE_DEVICE_PREFIX) is True
                )  # Default to True for safety (prevents accidental legacy treatment)
                assert (
                    result_data.get(USE_CIRCUIT_NUMBERS) is False
                )  # Default for existing installations (circuit numbers off by default)
