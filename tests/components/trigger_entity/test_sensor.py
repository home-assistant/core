"""Test trigger entity."""

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component


async def test_it_works(hass):
    """Test it works."""
    assert await async_setup_component(
        hass,
        "trigger_entity",
        {
            "trigger_entity": {
                "unique_id": "listening-test-event",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "sensor": {
                    "name": "Hello",
                    "unique_id": "just_a_test",
                    "device_class": "battery",
                    "unit_of_measurement": "%",
                    "state": "{{ trigger.event.data.beer }}",
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
    assert state.attributes.get("device_class") == "battery"
    assert state.attributes.get("unit_of_measurement") == "%"
    assert state.context is context

    ent_reg = entity_registry.async_get(hass)
    assert len(ent_reg.entities) == 1
    assert (
        ent_reg.entities["sensor.hello"].unique_id == "listening-test-event-just_a_test"
    )


async def test_render_error(hass, caplog):
    """Test it works."""
    assert await async_setup_component(
        hass,
        "trigger_entity",
        {
            "trigger_entity": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "sensor": {
                    "unique_id": "no-base-id",
                    "name": "Hello",
                    "state": "{{ non_existing + 1 }}",
                },
            },
        },
    )

    await hass.async_block_till_done()
    assert "Ignoring unique ID no-base-id" in caplog.text

    state = hass.states.get("sensor.hello")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 2}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.hello")
    assert state.state == STATE_UNAVAILABLE

    ent_reg = entity_registry.async_get(hass)
    assert len(ent_reg.entities) == 0
