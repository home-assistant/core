"""Test entity state conversion, identifiers and sensor attribute definitions."""

from homeassistant.components.visonic.visonic_entity_types import (
    AlarmPanelData,
    PanelState,
)


def test_panel_state_as_dict() -> None:
    """Flatten panel attributes alongside the typed state fields."""
    panel = PanelState(
        "standard",
        "none",
        100,
        False,
        attributes={"model": "PowerMaster"},
    )
    assert panel.as_dict() == {
        "emulationmode": "standard",
        "trouble": "none",
        "battery_level": 100,
        "tamper": False,
        "model": "PowerMaster",
    }


def test_alarm_panel_description() -> None:
    """Include the stable panel identifier in its log description."""
    assert str(AlarmPanelData("Visonic Alarm P1")) == "identifier='Visonic Alarm P1'"
