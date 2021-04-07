"""Test automation logbook."""
from homeassistant.components import automation, logbook
from homeassistant.core import Context
from homeassistant.setup import async_setup_component

from tests.components.logbook.test_init import MockLazyEventPartialState


async def test_humanify_automation_trigger_event(hass):
    """Test humanifying Shelly click event."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "automation", {})
    assert await async_setup_component(hass, "logbook", {})
    entity_attr_cache = logbook.EntityAttributeCache(hass)
    context = Context()

    event1, event2 = list(
        logbook.humanify(
            hass,
            [
                MockLazyEventPartialState(
                    automation.EVENT_AUTOMATION_TRIGGERED,
                    {
                        "name": "Bla",
                        "entity_id": "automation.bla",
                        "source": "state change of input_boolean.yo",
                    },
                    context=context,
                ),
                MockLazyEventPartialState(
                    automation.EVENT_AUTOMATION_TRIGGERED,
                    {
                        "name": "Bla",
                        "entity_id": "automation.bla",
                    },
                    context=context,
                ),
            ],
            entity_attr_cache,
            {},
        )
    )

    assert event1["name"] == "Bla"
    assert event1["message"] == "has been triggered by state change of input_boolean.yo"
    assert event1["source"] == "state change of input_boolean.yo"
    assert event1["context_id"] == context.id
    assert event1["entity_id"] == "automation.bla"

    assert event2["name"] == "Bla"
    assert event2["message"] == "has been triggered"
    assert event2["source"] is None
    assert event2["context_id"] == context.id
    assert event2["entity_id"] == "automation.bla"
