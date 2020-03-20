"""The lock tests for the august platform."""

from homeassistant.const import STATE_OFF

from .util import async_init_integration


async def test_automation_switches(hass):
    """Test creation automation switches."""

    await async_init_integration(hass)

    state = hass.states.get("switch.away_short")
    assert state.state == STATE_OFF
    expected_attributes = {
        "attribution": "Data provided by mynexia.com",
        "description": "When IFTTT activates the automation Upstairs "
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
        "change Fan Mode to Auto",
        "friendly_name": "Away Short",
        "icon": "mdi:script-text-outline",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())

    state = hass.states.get("switch.power_outage")
    assert state.state == STATE_OFF
    expected_attributes = {
        "attribution": "Data provided by mynexia.com",
        "description": "When IFTTT activates the automation Upstairs "
        "West Wing will permanently hold the heat to 55.0 "
        "and cool to 90.0 AND Downstairs East Wing will "
        "permanently hold the heat to 55.0 and cool to "
        "90.0 AND Downstairs West Wing will permanently "
        "hold the heat to 55.0 and cool to 90.0 AND "
        "Activate the mode named 'Power Outage'",
        "friendly_name": "Power Outage",
        "icon": "mdi:script-text-outline",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())

    state = hass.states.get("switch.power_restored")
    assert state.state == STATE_OFF
    expected_attributes = {
        "attribution": "Data provided by mynexia.com",
        "description": "When IFTTT activates the automation Upstairs "
        "West Wing will Run Schedule AND Downstairs East "
        "Wing will Run Schedule AND Downstairs West Wing "
        "will Run Schedule AND Activate the mode named "
        "'Home'",
        "friendly_name": "Power Restored",
        "icon": "mdi:script-text-outline",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())
