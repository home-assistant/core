"""Test script for tabs attribute functionality."""

from span_panel_api import SpanCircuitSnapshot

from homeassistant.components.span_panel.helpers import (
    construct_tabs_attribute,
    construct_voltage_attribute,
    get_circuit_voltage_type,
    parse_tabs_attribute,
)


def _make_circuit(
    tabs: list[int], instant_power_w: float = 100.0
) -> SpanCircuitSnapshot:
    """Create a minimal SpanCircuitSnapshot for tab/voltage tests."""
    return SpanCircuitSnapshot(
        circuit_id="test",
        name="Test Circuit",
        relay_state="CLOSED",
        instant_power_w=instant_power_w,
        produced_energy_wh=0.0,
        consumed_energy_wh=0.0,
        tabs=tabs,
        priority="NEVER",
        is_user_controllable=True,
        is_sheddable=True,
        is_never_backup=False,
    )


def test_tabs_attribute_construction() -> None:
    """Test tabs attribute construction from circuit data."""
    # Single tab (120V)
    assert construct_tabs_attribute(_make_circuit([28])) == "tabs [28]"

    # Two tabs (240V)
    assert construct_tabs_attribute(_make_circuit([30, 32])) == "tabs [30:32]"

    # No tabs
    assert construct_tabs_attribute(_make_circuit([])) is None

    # More than 2 tabs (invalid for US electrical system)
    assert construct_tabs_attribute(_make_circuit([1, 3, 5])) is None


def test_tabs_attribute_parsing() -> None:
    """Test tabs attribute parsing back to tab numbers."""
    assert parse_tabs_attribute("tabs [28]") == [28]
    assert parse_tabs_attribute("tabs [30:32]") == [30, 32]
    assert parse_tabs_attribute("invalid format") is None
    assert parse_tabs_attribute("tabs [invalid]") is None
    assert parse_tabs_attribute("tabs [1,3,5]") is None


def test_voltage_type_detection() -> None:
    """Test voltage type detection from circuit data."""
    assert get_circuit_voltage_type(_make_circuit([28])) == "120V"
    assert get_circuit_voltage_type(_make_circuit([30, 32])) == "240V"
    assert get_circuit_voltage_type(_make_circuit([])) == "unknown"
    assert get_circuit_voltage_type(_make_circuit([1, 3, 5])) == "unknown"


def test_voltage_attribute_construction() -> None:
    """Test voltage attribute construction from circuit data."""
    assert construct_voltage_attribute(_make_circuit([28])) == 120
    assert construct_voltage_attribute(_make_circuit([30, 32])) == 240
    assert construct_voltage_attribute(_make_circuit([])) is None
    assert construct_voltage_attribute(_make_circuit([1, 3, 5])) is None


def test_end_to_end_tabs_workflow() -> None:
    """Test the complete workflow from circuit data to tabs attribute and back."""
    circuit = _make_circuit([30, 32])

    tabs_attr = construct_tabs_attribute(circuit)
    assert tabs_attr == "tabs [30:32]"

    parsed_tabs = parse_tabs_attribute(tabs_attr)
    assert parsed_tabs == [30, 32]

    assert get_circuit_voltage_type(circuit) == "240V"
    assert construct_voltage_attribute(circuit) == 240


def test_amperage_calculation() -> None:
    """Test amperage calculation using voltage and power."""
    # 120V at 1200W -> 10A
    circuit_120v = _make_circuit([28], instant_power_w=1200.0)
    voltage_120v = construct_voltage_attribute(circuit_120v)
    assert voltage_120v is not None
    assert circuit_120v.instant_power_w / voltage_120v == 10.0

    # 240V at 4800W -> 20A
    circuit_240v = _make_circuit([30, 32], instant_power_w=4800.0)
    voltage_240v = construct_voltage_attribute(circuit_240v)
    assert voltage_240v is not None
    assert circuit_240v.instant_power_w / voltage_240v == 20.0

    # 0W -> 0A
    circuit_zero = _make_circuit([28], instant_power_w=0.0)
    voltage_zero = construct_voltage_attribute(circuit_zero)
    assert voltage_zero is not None
    assert circuit_zero.instant_power_w / voltage_zero == 0.0
