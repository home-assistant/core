"""Tests for the nexia scene (automation) platform."""

from nexia.home import NexiaHome

from homeassistant.core import HomeAssistant

from .conftest import setup_integration


async def test_automation_scenes(
    hass: HomeAssistant, mock_nexia_home: NexiaHome
) -> None:
    """Test creation automation scenes."""

    await setup_integration(hass, mock_nexia_home)

    state = hass.states.get("scene.away_short")
    assert state is not None
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "description": "Sets all zones to away temps.",
        "friendly_name": "Away Short",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("scene.power_outage")
    assert state is not None
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "description": "Hold zones at 55, 90 °F",
        "friendly_name": "Power Outage",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("scene.power_restored")
    assert state is not None
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "description": "Return to Run Schedule",
        "friendly_name": "Power Restored",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )
