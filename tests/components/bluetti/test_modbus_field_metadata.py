"""Tests for the field-name -> HA entity metadata mapping for Modbus sensors."""

from homeassistant.components.bluetti.modbus_field_metadata import (
    MODBUS_FIELD_METADATA,
    modbus_metadata_for,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory


def test_known_power_field() -> None:
    """Known power field."""
    metadata = modbus_metadata_for("ac_o_p_total")
    assert metadata.device_class == SensorDeviceClass.POWER
    assert metadata.state_class == SensorStateClass.MEASUREMENT
    assert metadata.category is None


def test_known_diagnostic_energy_field() -> None:
    """Known diagnostic energy field."""
    metadata = modbus_metadata_for("b_i_e")
    assert metadata.device_class == SensorDeviceClass.ENERGY
    assert metadata.state_class == SensorStateClass.TOTAL_INCREASING
    assert metadata.category == EntityCategory.DIAGNOSTIC


def test_known_config_field() -> None:
    """Known config field."""
    metadata = modbus_metadata_for("b_soc_high")
    assert metadata.device_class is None
    assert metadata.state_class is None
    assert metadata.category == EntityCategory.CONFIG


def test_switch_field_has_no_metadata() -> None:
    """Switch field has no metadata."""
    metadata = modbus_metadata_for("ac_o_switch")
    assert metadata.device_class is None
    assert metadata.state_class is None
    assert metadata.category is None


def test_unknown_field_returns_metadata_less_default() -> None:
    """Unknown field returns metadata less default."""
    metadata = modbus_metadata_for("not_a_real_field")
    assert metadata.device_class is None
    assert metadata.state_class is None
    assert metadata.category is None


def test_every_entry_has_at_least_one_attribute_or_is_a_deliberate_switch() -> None:
    """Every entry has at least one attribute or is a deliberate switch."""
    # Guards against a copy-paste ModbusFieldMetadata() placeholder that
    # should have carried real metadata.
    deliberately_bare = {"ac_o_switch", "g_i_switch", "g_o_switch"}
    for name, metadata in MODBUS_FIELD_METADATA.items():
        if name in deliberately_bare:
            continue
        assert metadata.device_class or metadata.state_class or metadata.category, (
            f"{name} has no metadata at all - is that intentional?"
        )
