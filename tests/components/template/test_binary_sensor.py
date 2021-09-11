"""The tests for the Template Binary sensor platform."""
from datetime import timedelta
import logging
from unittest.mock import patch

import pytest

from homeassistant import setup
from homeassistant.components import binary_sensor
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Context, CoreState
from homeassistant.helpers import entity_registry
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

ON = "on"
OFF = "off"


@pytest.mark.parametrize("count,domain", [(1, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test": {
                        "friendly_name": "virtual thingy",
                        "value_template": "{{ True }}",
                        "device_class": "motion",
                    }
                },
            },
        },
    ],
)
async def test_setup_legacy(hass, start_ha):
    """Test the setup."""
    state = hass.states.get("binary_sensor.test")
    assert state is not None
    assert state.name == "virtual thingy"
    assert state.state == ON
    assert state.attributes["device_class"] == "motion"


@pytest.mark.parametrize("count,domain", [(0, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {"binary_sensor": {"platform": "template"}},
        {"binary_sensor": {"platform": "template", "sensors": {"foo bar": {}}}},
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test": {
                        "value_template": "{{ foo }}",
                        "device_class": "foobarnotreal",
                    }
                },
            }
        },
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {"test": {"device_class": "motion"}},
            }
        },
    ],
)
async def test_setup_invalid_sensors(hass, count, start_ha):
    """Test setup with no sensors."""
    assert len(hass.states.async_entity_ids()) == count


@pytest.mark.parametrize("count,domain", [(1, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {
                        "value_template": "{{ states.sensor.xyz.state }}",
                        "icon_template": "{% if "
                        "states.binary_sensor.test_state.state == "
                        "'Works' %}"
                        "mdi:check"
                        "{% endif %}",
                    },
                },
            },
        },
    ],
)
async def test_icon_template(hass, start_ha):
    """Test icon template."""
    state = hass.states.get("binary_sensor.test_template_sensor")
    assert state.attributes.get("icon") == ""

    hass.states.async_set("binary_sensor.test_state", "Works")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_template_sensor")
    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize("count,domain", [(1, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {
                        "value_template": "{{ states.sensor.xyz.state }}",
                        "entity_picture_template": "{% if "
                        "states.binary_sensor.test_state.state == "
                        "'Works' %}"
                        "/local/sensor.png"
                        "{% endif %}",
                    },
                },
            },
        },
    ],
)
async def test_entity_picture_template(hass, start_ha):
    """Test entity_picture template."""
    state = hass.states.get("binary_sensor.test_template_sensor")
    assert state.attributes.get("entity_picture") == ""

    hass.states.async_set("binary_sensor.test_state", "Works")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_template_sensor")
    assert state.attributes["entity_picture"] == "/local/sensor.png"


@pytest.mark.parametrize("count,domain", [(1, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {
                        "value_template": "{{ states.sensor.xyz.state }}",
                        "attribute_templates": {
                            "test_attribute": "It {{ states.sensor.test_state.state }}."
                        },
                    },
                },
            },
        },
    ],
)
async def test_attribute_templates(hass, start_ha):
    """Test attribute_templates template."""
    state = hass.states.get("binary_sensor.test_template_sensor")
    assert state.attributes.get("test_attribute") == "It ."
    hass.states.async_set("sensor.test_state", "Works2")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "Works")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_template_sensor")
    assert state.attributes["test_attribute"] == "It Works."


@pytest.fixture
async def setup_mock():
    """Do setup of sensor mock."""
    with patch(
        "homeassistant.components.template.binary_sensor."
        "BinarySensorTemplate._update_state"
    ) as _update_state:
        yield _update_state


@pytest.mark.parametrize("count,domain", [(1, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "match_all_template_sensor": {
                        "value_template": (
                            "{% for state in states %}"
                            "{% if state.entity_id == 'sensor.humidity' %}"
                            "{{ state.entity_id }}={{ state.state }}"
                            "{% endif %}"
                            "{% endfor %}"
                        ),
                    },
                },
            }
        },
    ],
)
async def test_match_all(hass, setup_mock, start_ha):
    """Test template that is rerendered on any state lifecycle."""
    init_calls = len(setup_mock.mock_calls)

    hass.states.async_set("sensor.any_state", "update")
    await hass.async_block_till_done()
    assert len(setup_mock.mock_calls) == init_calls


@pytest.mark.parametrize("count,domain", [(1, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test": {
                        "friendly_name": "virtual thingy",
                        "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                        "device_class": "motion",
                    },
                },
            },
        },
    ],
)
async def test_event(hass, start_ha):
    """Test the event."""
    state = hass.states.get("binary_sensor.test")
    assert state.state == OFF

    hass.states.async_set("sensor.test_state", ON)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == ON


@pytest.mark.parametrize("count,domain", [(1, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test_on": {
                        "friendly_name": "virtual thingy",
                        "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                        "device_class": "motion",
                        "delay_on": 5,
                    },
                    "test_off": {
                        "friendly_name": "virtual thingy",
                        "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                        "device_class": "motion",
                        "delay_off": 5,
                    },
                },
            },
        },
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test_on": {
                        "friendly_name": "virtual thingy",
                        "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                        "device_class": "motion",
                        "delay_on": '{{ ({ "seconds": 10 / 2 }) }}',
                    },
                    "test_off": {
                        "friendly_name": "virtual thingy",
                        "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                        "device_class": "motion",
                        "delay_off": '{{ ({ "seconds": 10 / 2 }) }}',
                    },
                },
            },
        },
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test_on": {
                        "friendly_name": "virtual thingy",
                        "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                        "device_class": "motion",
                        "delay_on": '{{ ({ "seconds": states("input_number.delay")|int }) }}',
                    },
                    "test_off": {
                        "friendly_name": "virtual thingy",
                        "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                        "device_class": "motion",
                        "delay_off": '{{ ({ "seconds": states("input_number.delay")|int }) }}',
                    },
                },
            },
        },
    ],
)
async def test_template_delay_on_off(hass, start_ha):
    """Test binary sensor template delay on."""
    assert hass.states.get("binary_sensor.test_on").state == OFF
    assert hass.states.get("binary_sensor.test_off").state == OFF
    hass.states.async_set("input_number.delay", 5)
    hass.states.async_set("sensor.test_state", ON)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_on").state == OFF
    assert hass.states.get("binary_sensor.test_off").state == ON

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_on").state == ON
    assert hass.states.get("binary_sensor.test_off").state == ON

    # check with time changes
    hass.states.async_set("sensor.test_state", OFF)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_on").state == OFF
    assert hass.states.get("binary_sensor.test_off").state == ON

    hass.states.async_set("sensor.test_state", ON)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_on").state == OFF
    assert hass.states.get("binary_sensor.test_off").state == ON

    hass.states.async_set("sensor.test_state", OFF)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_on").state == OFF
    assert hass.states.get("binary_sensor.test_off").state == ON

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_on").state == OFF
    assert hass.states.get("binary_sensor.test_off").state == OFF


@pytest.mark.parametrize("count,domain", [(1, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test": {
                        "friendly_name": "virtual thingy",
                        "value_template": "true",
                        "device_class": "motion",
                        "delay_off": 5,
                    },
                },
            },
        },
    ],
)
async def test_available_without_availability_template(hass, start_ha):
    """Ensure availability is true without an availability_template."""
    state = hass.states.get("binary_sensor.test")

    assert state.state != STATE_UNAVAILABLE
    assert state.attributes[ATTR_DEVICE_CLASS] == "motion"


@pytest.mark.parametrize("count,domain", [(1, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test": {
                        "friendly_name": "virtual thingy",
                        "value_template": "true",
                        "device_class": "motion",
                        "delay_off": 5,
                        "availability_template": "{{ is_state('sensor.test_state','on') }}",
                    },
                },
            },
        },
    ],
)
async def test_availability_template(hass, start_ha):
    """Test availability template."""
    hass.states.async_set("sensor.test_state", STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.test").state == STATE_UNAVAILABLE

    hass.states.async_set("sensor.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")

    assert state.state != STATE_UNAVAILABLE
    assert state.attributes[ATTR_DEVICE_CLASS] == "motion"


@pytest.mark.parametrize("count,domain", [(1, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "invalid_template": {
                        "value_template": "{{ states.binary_sensor.test_sensor }}",
                        "attribute_templates": {
                            "test_attribute": "{{ states.binary_sensor.unknown.attributes.picture }}"
                        },
                    }
                },
            },
        },
    ],
)
async def test_invalid_attribute_template(hass, start_ha, caplog_setup_text):
    """Test that errors are logged if rendering template fails."""
    hass.states.async_set("binary_sensor.test_sensor", "true")
    assert len(hass.states.async_all()) == 2
    assert ("test_attribute") in caplog_setup_text
    assert ("TemplateError") in caplog_setup_text


@pytest.mark.parametrize("count,domain", [(1, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "my_sensor": {
                        "value_template": "{{ states.binary_sensor.test_sensor }}",
                        "availability_template": "{{ x - 12 }}",
                    },
                },
            },
        },
    ],
)
async def test_invalid_availability_template_keeps_component_available(
    hass, start_ha, caplog_setup_text
):
    """Test that an invalid availability keeps the device available."""

    assert hass.states.get("binary_sensor.my_sensor").state != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog_setup_text


async def test_no_update_template_match_all(hass, caplog):
    """Test that we do not update sensors that match on all."""

    hass.state = CoreState.not_running

    await setup.async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "all_state": {"value_template": '{{ "true" }}'},
                    "all_icon": {
                        "value_template": "{{ states.binary_sensor.test_sensor.state }}",
                        "icon_template": "{{ 1 + 1 }}",
                    },
                    "all_entity_picture": {
                        "value_template": "{{ states.binary_sensor.test_sensor.state }}",
                        "entity_picture_template": "{{ 1 + 1 }}",
                    },
                    "all_attribute": {
                        "value_template": "{{ states.binary_sensor.test_sensor.state }}",
                        "attribute_templates": {"test_attribute": "{{ 1 + 1 }}"},
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.test_sensor", "true")
    assert len(hass.states.async_all()) == 5

    assert hass.states.get("binary_sensor.all_state").state == OFF
    assert hass.states.get("binary_sensor.all_icon").state == OFF
    assert hass.states.get("binary_sensor.all_entity_picture").state == OFF
    assert hass.states.get("binary_sensor.all_attribute").state == OFF

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.all_state").state == ON
    assert hass.states.get("binary_sensor.all_icon").state == ON
    assert hass.states.get("binary_sensor.all_entity_picture").state == ON
    assert hass.states.get("binary_sensor.all_attribute").state == ON

    hass.states.async_set("binary_sensor.test_sensor", "false")
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.all_state").state == ON
    # Will now process because we have one valid template
    assert hass.states.get("binary_sensor.all_icon").state == OFF
    assert hass.states.get("binary_sensor.all_entity_picture").state == OFF
    assert hass.states.get("binary_sensor.all_attribute").state == OFF

    await hass.helpers.entity_component.async_update_entity("binary_sensor.all_state")
    await hass.helpers.entity_component.async_update_entity("binary_sensor.all_icon")
    await hass.helpers.entity_component.async_update_entity(
        "binary_sensor.all_entity_picture"
    )
    await hass.helpers.entity_component.async_update_entity(
        "binary_sensor.all_attribute"
    )

    assert hass.states.get("binary_sensor.all_state").state == ON
    assert hass.states.get("binary_sensor.all_icon").state == OFF
    assert hass.states.get("binary_sensor.all_entity_picture").state == OFF
    assert hass.states.get("binary_sensor.all_attribute").state == OFF


@pytest.mark.parametrize("count,domain", [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "unique_id": "group-id",
                "binary_sensor": {
                    "name": "top-level",
                    "unique_id": "sensor-id",
                    "state": ON,
                },
            },
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_cover_01": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ true }}",
                    },
                    "test_template_cover_02": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ false }}",
                    },
                },
            },
        },
    ],
)
async def test_unique_id(hass, start_ha):
    """Test unique_id option only creates one binary sensor per id."""
    assert len(hass.states.async_all()) == 2

    ent_reg = entity_registry.async_get(hass)

    assert len(ent_reg.entities) == 2
    assert (
        ent_reg.async_get_entity_id("binary_sensor", "template", "group-id-sensor-id")
        is not None
    )
    assert (
        ent_reg.async_get_entity_id(
            "binary_sensor", "template", "not-so-unique-anymore"
        )
        is not None
    )


@pytest.mark.parametrize("count,domain", [(1, binary_sensor.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test": {
                        "friendly_name": "virtual thingy",
                        "value_template": "True",
                        "icon_template": "{{ states.sensor.test_state.state }}",
                        "device_class": "motion",
                        "delay_on": 5,
                    },
                },
            },
        },
    ],
)
async def test_template_validation_error(hass, caplog, start_ha):
    """Test binary sensor template delay on."""
    caplog.set_level(logging.ERROR)
    state = hass.states.get("binary_sensor.test")
    assert state.attributes.get("icon") == ""

    hass.states.async_set("sensor.test_state", "mdi:check")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.attributes.get("icon") == "mdi:check"

    hass.states.async_set("sensor.test_state", "invalid_icon")
    await hass.async_block_till_done()
    assert len(caplog.records) == 1
    assert caplog.records[0].message.startswith(
        "Error validating template result 'invalid_icon' from template"
    )

    state = hass.states.get("binary_sensor.test")
    assert state.attributes.get("icon") is None


@pytest.mark.parametrize("count,domain", [(2, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": [
                {"invalid": "config"},
                # Config after invalid should still be set up
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "binary_sensors": {
                        "hello": {
                            "friendly_name": "Hello Name",
                            "unique_id": "hello_name-id",
                            "device_class": "battery",
                            "value_template": "{{ trigger.event.data.beer == 2 }}",
                            "entity_picture_template": "{{ '/local/dogs.png' }}",
                            "icon_template": "{{ 'mdi:pirate' }}",
                            "attribute_templates": {
                                "plus_one": "{{ trigger.event.data.beer + 1 }}"
                            },
                        },
                    },
                    "binary_sensor": [
                        {
                            "name": "via list",
                            "unique_id": "via_list-id",
                            "device_class": "battery",
                            "state": "{{ trigger.event.data.beer == 2 }}",
                            "picture": "{{ '/local/dogs.png' }}",
                            "icon": "{{ 'mdi:pirate' }}",
                            "attributes": {
                                "plus_one": "{{ trigger.event.data.beer + 1 }}",
                                "another": "{{ trigger.event.data.uno_mas or 1 }}",
                            },
                        }
                    ],
                },
                {
                    "trigger": [],
                    "binary_sensors": {
                        "bare_minimum": {
                            "value_template": "{{ trigger.event.data.beer == 1 }}"
                        },
                    },
                },
            ],
        },
    ],
)
async def test_trigger_entity(hass, start_ha):
    """Test trigger entity works."""
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.hello_name")
    assert state is not None
    assert state.state == OFF

    state = hass.states.get("binary_sensor.bare_minimum")
    assert state is not None
    assert state.state == OFF

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 2}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.hello_name")
    assert state.state == ON
    assert state.attributes.get("device_class") == "battery"
    assert state.attributes.get("icon") == "mdi:pirate"
    assert state.attributes.get("entity_picture") == "/local/dogs.png"
    assert state.attributes.get("plus_one") == 3
    assert state.context is context

    ent_reg = entity_registry.async_get(hass)
    assert len(ent_reg.entities) == 2
    assert (
        ent_reg.entities["binary_sensor.hello_name"].unique_id
        == "listening-test-event-hello_name-id"
    )
    assert (
        ent_reg.entities["binary_sensor.via_list"].unique_id
        == "listening-test-event-via_list-id"
    )

    state = hass.states.get("binary_sensor.via_list")
    assert state.state == ON
    assert state.attributes.get("device_class") == "battery"
    assert state.attributes.get("icon") == "mdi:pirate"
    assert state.attributes.get("entity_picture") == "/local/dogs.png"
    assert state.attributes.get("plus_one") == 3
    assert state.attributes.get("another") == 1
    assert state.context is context

    # Even if state itself didn't change, attributes might have changed
    hass.bus.async_fire("test_event", {"beer": 2, "uno_mas": "si"})
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.via_list")
    assert state.state == ON
    assert state.attributes.get("another") == "si"


@pytest.mark.parametrize("count,domain", [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "binary_sensor": {
                    "name": "test",
                    "state": "{{ trigger.event.data.beer == 2 }}",
                    "device_class": "motion",
                    "delay_on": '{{ ({ "seconds": 6 / 2 }) }}',
                    "auto_off": '{{ ({ "seconds": 1 + 1 }) }}',
                },
            },
        },
    ],
)
async def test_template_with_trigger_templated_delay_on(hass, start_ha):
    """Test binary sensor template with template delay on."""
    state = hass.states.get("binary_sensor.test")
    assert state.state == OFF

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 2}, context=context)
    await hass.async_block_till_done()

    future = dt_util.utcnow() + timedelta(seconds=3)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == ON

    # Now wait for the auto-off
    future = dt_util.utcnow() + timedelta(seconds=2)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == OFF
