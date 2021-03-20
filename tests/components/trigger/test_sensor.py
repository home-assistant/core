""""Test trigger entity."""

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import Context
from homeassistant.setup import async_setup_component


async def test_it_works(hass):
    """Test it works."""
    assert await async_setup_component(
        hass,
        "trigger",
        {
            "trigger": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "sensor": {
                    "just_a_test": {
                        "name": "Hello",
                        "value_template": "{{ trigger.event.data.beer }}",
                    }
                },
            },
        },
    )

    await hass.async_block_till_done()

    state = hass.states.get("sensor.hello")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 2}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.hello")
    assert state.state == "2"
    assert state.context is context
