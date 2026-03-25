"""Tests for unique ID generation pure functions in Span Panel integration.

These tests exercise the actual build_*_unique_id helpers and
get_user_friendly_suffix / get_panel_entity_suffix functions that
produce the unique IDs stored in the entity registry.
"""

from homeassistant.components.span_panel.helpers import (
    build_binary_sensor_unique_id,
    build_circuit_unique_id,
    build_panel_unique_id,
    build_select_unique_id,
    build_switch_unique_id,
    get_panel_entity_suffix,
    get_user_friendly_suffix,
)


class TestBuildCircuitUniqueId:
    """Tests for build_circuit_unique_id."""

    def test_basic_format(self) -> None:
        """Circuit unique IDs follow span_{serial}_{circuit_id}_{suffix}."""
        uid = build_circuit_unique_id("SP3-001", "uuid-kitchen", "instantPowerW")
        assert uid == "span_sp3-001_uuid-kitchen_power"

    def test_serial_lowercased(self) -> None:
        """Serial numbers are lowercased for consistency."""
        uid = build_circuit_unique_id("ABC123DEF", "1", "instantPowerW")
        assert uid.startswith("span_abc123def_")

    def test_different_serials_produce_different_ids(self) -> None:
        """Two panels with the same circuit produce distinct unique IDs."""
        uid1 = build_circuit_unique_id("PANEL001", "1", "instantPowerW")
        uid2 = build_circuit_unique_id("PANEL002", "1", "instantPowerW")
        assert uid1 != uid2

    def test_different_circuits_produce_different_ids(self) -> None:
        """Same panel, different circuits produce distinct unique IDs."""
        uid1 = build_circuit_unique_id("SP3-001", "1", "instantPowerW")
        uid2 = build_circuit_unique_id("SP3-001", "2", "instantPowerW")
        assert uid1 != uid2

    def test_different_description_keys_produce_different_ids(self) -> None:
        """Same circuit, different sensor types produce distinct unique IDs."""
        uid_power = build_circuit_unique_id("SP3-001", "1", "instantPowerW")
        uid_energy = build_circuit_unique_id("SP3-001", "1", "consumedEnergyWh")
        assert uid_power != uid_energy

    def test_energy_consumed_suffix(self) -> None:
        """ConsumedEnergyWh maps to the expected suffix."""
        uid = build_circuit_unique_id("SP3-001", "1", "consumedEnergyWh")
        assert uid.endswith("_energy_consumed")

    def test_energy_produced_suffix(self) -> None:
        """ProducedEnergyWh maps to the expected suffix."""
        uid = build_circuit_unique_id("SP3-001", "1", "producedEnergyWh")
        assert uid.endswith("_energy_produced")

    def test_unmapped_key_passes_through_lowercased(self) -> None:
        """Keys without a suffix mapping are lowercased as-is."""
        uid = build_circuit_unique_id("SP3-001", "1", "someNewField")
        assert uid.endswith("_somenewfield")


class TestBuildPanelUniqueId:
    """Tests for build_panel_unique_id."""

    def test_basic_format(self) -> None:
        """Panel unique IDs follow span_{serial}_{entity_suffix}."""
        uid = build_panel_unique_id("SP3-001", "instantGridPowerW")
        assert uid == "span_sp3-001_current_power"

    def test_serial_lowercased(self) -> None:
        """Serial numbers are lowercased."""
        uid = build_panel_unique_id("ABC123", "instantGridPowerW")
        assert uid.startswith("span_abc123_")

    def test_feedthrough_power_suffix(self) -> None:
        """FeedthroughPowerW uses its panel-specific suffix mapping."""
        uid = build_panel_unique_id("SP3-001", "feedthroughPowerW")
        assert uid.endswith("_feed_through_power")


class TestBuildSwitchUniqueId:
    """Tests for build_switch_unique_id."""

    def test_format(self) -> None:
        """Switch unique IDs follow span_{serial}_relay_{circuit_id}."""
        uid = build_switch_unique_id("SP3-001", "uuid-kitchen")
        assert uid == "span_SP3-001_relay_uuid-kitchen"


class TestBuildBinarySensorUniqueId:
    """Tests for build_binary_sensor_unique_id."""

    def test_format(self) -> None:
        """Binary sensor unique IDs follow span_{serial}_{key}."""
        uid = build_binary_sensor_unique_id("SP3-001", "doorState")
        assert uid == "span_SP3-001_doorState"


class TestBuildSelectUniqueId:
    """Tests for build_select_unique_id."""

    def test_format(self) -> None:
        """Select unique IDs follow span_{serial}_select_{select_id}."""
        uid = build_select_unique_id("SP3-001", "uuid-kitchen")
        assert uid == "span_SP3-001_select_uuid-kitchen"


class TestGetUserFriendlySuffix:
    """Tests for the suffix mapping used by circuit unique IDs."""

    def test_known_power_key(self) -> None:
        """InstantPowerW maps to 'power'."""
        assert get_user_friendly_suffix("instantPowerW") == "power"

    def test_known_energy_keys(self) -> None:
        """Energy keys map to human-readable suffixes."""
        assert get_user_friendly_suffix("consumedEnergyWh") == "energy_consumed"
        assert get_user_friendly_suffix("producedEnergyWh") == "energy_produced"

    def test_unknown_key_lowercased(self) -> None:
        """Unknown keys pass through lowercased."""
        assert get_user_friendly_suffix("novelMetric") == "novelmetric"

    def test_dotted_key_underscored(self) -> None:
        """Dots in keys are replaced with underscores."""
        assert get_user_friendly_suffix("some.dotted.key") == "some_dotted_key"


class TestGetPanelEntitySuffix:
    """Tests for the panel-specific suffix mapping."""

    def test_panel_specific_mapping(self) -> None:
        """Panel keys use their own mapping (not the circuit one)."""
        assert get_panel_entity_suffix("instantGridPowerW") == "current_power"

    def test_falls_back_to_general(self) -> None:
        """Keys not in the panel mapping fall back to the general suffix map."""
        assert get_panel_entity_suffix("instantPowerW") == "power"

    def test_unknown_key_lowercased(self) -> None:
        """Unmapped keys pass through lowercased."""
        assert get_panel_entity_suffix("brandNewField") == "brandnewfield"
