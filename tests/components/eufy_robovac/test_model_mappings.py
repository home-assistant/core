"""Tests for Eufy RoboVac model mappings."""

from homeassistant.components.eufy_robovac.const import RoboVacCommand
from homeassistant.components.eufy_robovac.model_mappings import MODEL_MAPPINGS


def test_t2253_mapping_exists() -> None:
    """The G30 Hybrid model mapping should exist."""
    assert "T2253" in MODEL_MAPPINGS


def test_t2253_command_codes() -> None:
    """T2253 should expose expected DPS command codes."""
    mapping = MODEL_MAPPINGS["T2253"]

    assert mapping.commands[RoboVacCommand.START_PAUSE] == 2
    assert mapping.commands[RoboVacCommand.MODE] == 5
    assert mapping.commands[RoboVacCommand.RETURN_HOME] == 101
    assert mapping.commands[RoboVacCommand.FAN_SPEED] == 102


def test_t2253_mode_and_fan_values() -> None:
    """T2253 value mappings should include key control modes."""
    mapping = MODEL_MAPPINGS["T2253"]

    assert mapping.mode_values["auto"] == "Auto"
    assert mapping.mode_values["small_room"] == "SmallRoom"
    assert mapping.mode_values["edge"] == "Edge"
    assert mapping.fan_speed_values["boost_iq"] == "Boost_IQ"
    assert mapping.error_values["0"] == "No error"
