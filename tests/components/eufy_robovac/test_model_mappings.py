"""Tests for Eufy RoboVac model mappings."""

import pytest

from homeassistant.components.eufy_robovac.const import RoboVacCommand
from homeassistant.components.eufy_robovac.model_mappings import MODEL_MAPPINGS


SUPPORTED_MODELS = {
    "T2118",
    "T2128",
    "T2181",
    "T2193",
    "T2194",
    "T2251",
    "T2252",
    "T2253",
    "T2254",
    "T2255",
    "T2259",
    "T2261",
    "T2262",
    "T2268",
}


def test_supported_model_mappings_exist() -> None:
    """All imported high-confidence model mappings should exist."""
    assert SUPPORTED_MODELS.issubset(MODEL_MAPPINGS)


@pytest.mark.parametrize("model_code", sorted(SUPPORTED_MODELS))
def test_common_command_codes(model_code: str) -> None:
    """Imported models should expose expected common DPS command codes."""
    mapping = MODEL_MAPPINGS[model_code]

    assert mapping.commands[RoboVacCommand.START_PAUSE] == 2
    assert mapping.commands[RoboVacCommand.MODE] == 5
    assert mapping.commands[RoboVacCommand.STATUS] == 15
    assert mapping.commands[RoboVacCommand.RETURN_HOME] == 101
    assert mapping.commands[RoboVacCommand.LOCATE] == 103
    assert mapping.commands[RoboVacCommand.BATTERY] == 104
    assert mapping.commands[RoboVacCommand.ERROR] == 106


@pytest.mark.parametrize("model_code", sorted(SUPPORTED_MODELS))
def test_common_mode_values(model_code: str) -> None:
    """Imported models should keep the standard core mode values."""
    mapping = MODEL_MAPPINGS[model_code]

    assert mapping.mode_values["auto"] == "Auto"
    assert mapping.mode_values["small_room"] == "SmallRoom"
    assert mapping.mode_values["spot"] == "Spot"
    assert mapping.mode_values["edge"] == "Edge"
    assert mapping.mode_values["nosweep"] == "Nosweep"


def test_t2253_fan_values() -> None:
    """T2253 should keep boost_iq fan-speed mapping."""
    mapping = MODEL_MAPPINGS["T2253"]

    assert mapping.fan_speed_values["standard"] == "Standard"
    assert mapping.fan_speed_values["turbo"] == "Turbo"
    assert mapping.fan_speed_values["max"] == "Max"
    assert mapping.fan_speed_values["boost_iq"] == "Boost_IQ"


def test_t2194_fan_code_and_values() -> None:
    """T2194 should use the model-specific fan code and quiet mode values."""
    mapping = MODEL_MAPPINGS["T2194"]

    assert mapping.commands[RoboVacCommand.FAN_SPEED] == 130
    assert mapping.fan_speed_values["quiet"] == "Quiet"
    assert "boost_iq" not in mapping.fan_speed_values


@pytest.mark.parametrize("model_code", ["T2181", "T2193", "T2261", "T2262", "T2268"])
def test_pure_fan_models(model_code: str) -> None:
    """Specific models should expose pure fan mode used by their mappings."""
    mapping = MODEL_MAPPINGS[model_code]

    assert mapping.fan_speed_values["pure"] == "Quiet"
    assert "boost_iq" not in mapping.fan_speed_values


def test_error_values() -> None:
    """T2253 should expose expected baseline error value mapping."""
    mapping = MODEL_MAPPINGS["T2253"]

    assert mapping.error_values["0"] == "No error"
