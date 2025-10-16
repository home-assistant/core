"""Test Alexa handlers."""

import importlib

import pytest


@pytest.mark.parametrize(
    "key",
    [
        ("Alexa.ThermostatController", "SetTargetTemperature"),
        ("Alexa.ThermostatController", "AdjustTargetTemperature"),
        ("Alexa.ThermostatController", "SetThermostatMode"),
        ("Alexa.SecurityPanelController", "Arm"),
        ("Alexa.SecurityPanelController", "Disarm"),
    ],
)
async def test_handlers_registry_contains_expected_directives(key) -> None:
    """Test if handlers contains expected directives."""
    handlers_mod = importlib.import_module("homeassistant.components.alexa.handlers")
    registry = handlers_mod.HANDLERS
    func = registry.get(key)
    assert callable(func), f"Registry missing handler for {key}"
