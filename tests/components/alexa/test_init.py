"""Tests for alexa."""
from homeassistant.components.alexa.const import EVENT_ALEXA_SMART_HOME
from homeassistant.setup import async_setup_component

from tests.components.logbook.common import MockRow, mock_humanify


async def test_humanify_alexa_event(hass):
    """Test humanifying Alexa event."""
    hass.config.components.add("recorder")
    await async_setup_component(hass, "alexa", {})
    await async_setup_component(hass, "logbook", {})
    hass.states.async_set("light.kitchen", "on", {"friendly_name": "Kitchen Light"})

    results = mock_humanify(
        hass,
        [
            MockRow(
                EVENT_ALEXA_SMART_HOME,
                {"request": {"namespace": "Alexa.Discovery", "name": "Discover"}},
            ),
            MockRow(
                EVENT_ALEXA_SMART_HOME,
                {
                    "request": {
                        "namespace": "Alexa.PowerController",
                        "name": "TurnOn",
                        "entity_id": "light.kitchen",
                    }
                },
            ),
            MockRow(
                EVENT_ALEXA_SMART_HOME,
                {
                    "request": {
                        "namespace": "Alexa.PowerController",
                        "name": "TurnOn",
                        "entity_id": "light.non_existing",
                    }
                },
            ),
        ],
    )

    event1, event2, event3 = results

    assert event1["name"] == "Amazon Alexa"
    assert event1["message"] == "sent command Alexa.Discovery/Discover"
    assert event1["entity_id"] is None

    assert event2["name"] == "Amazon Alexa"
    assert (
        event2["message"]
        == "sent command Alexa.PowerController/TurnOn for Kitchen Light"
    )
    assert event2["entity_id"] == "light.kitchen"

    assert event3["name"] == "Amazon Alexa"
    assert (
        event3["message"]
        == "sent command Alexa.PowerController/TurnOn for light.non_existing"
    )
    assert event3["entity_id"] == "light.non_existing"
