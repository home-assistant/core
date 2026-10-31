"""Test Visonic types."""

from homeassistant.components.visonic.visonic_types import DeviceType, PanelCondition


def test_panelcondition_values() -> None:
    """Test panel condition."""
    assert PanelCondition.CONNECTION.value == 104
    assert PanelCondition.PANEL_LOG_ENTRY.name == "PANEL_LOG_ENTRY"


def test_string_enum_helpers() -> None:
    """Convert string enum values to and from display titles."""
    assert DeviceType.ETHERNET.title() == "Ethernet"
    assert DeviceType.from_title("  Cloud Server ") == DeviceType.CLOUD
