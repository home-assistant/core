import pytest
from homeassistant.core import HomeAssistant
from homeassistant.components.automation import automations_with_device

@pytest.fixture
def hass():
    """Set up HomeAssistant instance with alias data."""
    hass = HomeAssistant()
    hass.data["device_aliases"] = {
        "hot_tub_sensor_device": "61fbf77fb8093533d657f6f448854d56"
    }
    return hass

def test_valid_device_id_returns_result(hass):
    # Simulate _automations_with_x to track input
    called_with = {}
    def fake_automations_with_x(hass, device_id, key):
        called_with["device_id"] = device_id
        return ["automation.1"]
    # Patch the internal call
    from homeassistant.components.automation import _automations_with_x
    setattr(__import__("homeassistant.components.automation", fromlist=[""]), "_automations_with_x", fake_automations_with_x)

    result = automations_with_device(hass, "61fbf77fb8093533d657f6f448854d56")
    assert result == ["automation.1"]
    assert called_with["device_id"] == "61fbf77fb8093533d657f6f448854d56"

def test_valid_alias_resolves_to_device_id(hass):
    called_with = {}
    def fake_automations_with_x(hass, device_id, key):
        called_with["device_id"] = device_id
        return ["automation.2"]
    from homeassistant.components.automation import _automations_with_x
    setattr(__import__("homeassistant.components.automation", fromlist=[""]), "_automations_with_x", fake_automations_with_x)

    result = automations_with_device(hass, "hot_tub_sensor_device")
    assert result == ["automation.2"]
    assert called_with["device_id"] == "61fbf77fb8093533d657f6f448854d56"

def test_unknown_alias_logs_warning_and_returns_empty(hass, caplog):
    result = automations_with_device(hass, "unknown_alias")
    assert result == []
    assert "Unknown device alias: unknown_alias" in caplog.text
