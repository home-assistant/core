"""The scene tests for the nexia platform."""

from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_automation_scenes(hass: HomeAssistant) -> None:
    """Test creation automation scenes."""

    await async_init_integration(hass)

    state = hass.states.get("scene.away_short")
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "description": (
            "When IFTTT activates the automation Upstairs "
            "West Wing will permanently hold the heat to 63.0 "
            "and cool to 80.0 AND Downstairs East Wing will "
            "permanently hold the heat to 63.0 and cool to "
            "79.0 AND Downstairs West Wing will permanently "
            "hold the heat to 63.0 and cool to 79.0 AND "
            "Upstairs West Wing will permanently hold the "
            "heat to 63.0 and cool to 81.0 AND Upstairs West "
            "Wing will change Fan Mode to Auto AND Downstairs "
            "East Wing will change Fan Mode to Auto AND "
            "Downstairs West Wing will change Fan Mode to "
            "Auto AND Activate the mode named 'Away Short' "
            "AND Master Suite will permanently hold the heat "
            "to 63.0 and cool to 79.0 AND Master Suite will "
            "change Fan Mode to Auto"
        ),
        "friendly_name": "Away Short",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("scene.power_outage")
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "description": (
            "When IFTTT activates the automation Upstairs "
            "West Wing will permanently hold the heat to 55.0 "
            "and cool to 90.0 AND Downstairs East Wing will "
            "permanently hold the heat to 55.0 and cool to "
            "90.0 AND Downstairs West Wing will permanently "
            "hold the heat to 55.0 and cool to 90.0 AND "
            "Activate the mode named 'Power Outage'"
        ),
        "friendly_name": "Power Outage",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("scene.power_restored")
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "description": (
            "When IFTTT activates the automation Upstairs "
            "West Wing will Run Schedule AND Downstairs East "
            "Wing will Run Schedule AND Downstairs West Wing "
            "will Run Schedule AND Activate the mode named "
            "'Home'"
        ),
        "friendly_name": "Power Restored",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )
