"""Test automation logbook."""

from homeassistant.components import automation
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.logbook.common import MockRow, mock_humanify


async def test_humanify_automation_trigger_event(hass: HomeAssistant) -> None:
    """Test humanifying Shelly click event."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "automation", {})
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()
    context = Context()

    event1, event2 = mock_humanify(
        hass,
        [
            MockRow(
                automation.EVENT_AUTOMATION_TRIGGERED,
                {
                    "name": "Bla",
                    "entity_id": "automation.bla",
                    "source": "state change of input_boolean.yo",
                },
                context=context,
            ),
            MockRow(
                automation.EVENT_AUTOMATION_TRIGGERED,
                {
                    "name": "Bla",
                    "entity_id": "automation.bla",
                },
                context=context,
            ),
        ],
    )

    assert event1["name"] == "Bla"
    assert event1["message"] == "triggered by state change of input_boolean.yo"
    assert event1["source"] == "state change of input_boolean.yo"
    assert event1["context_id"] == context.id
    assert event1["entity_id"] == "automation.bla"

    assert event2["name"] == "Bla"
    assert event2["message"] == "triggered"
    assert event2["source"] is None
    assert event2["context_id"] == context.id
    assert event2["entity_id"] == "automation.bla"
