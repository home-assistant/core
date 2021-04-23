"""The tests for the Template Binary sensor platform."""
from datetime import timedelta
import logging
from unittest.mock import patch

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


async def test_setup_legacy(hass):
    """Test the setup."""
    config = {
        "binary_sensor": {
            "platform": "template",
            "sensors": {
                "test": {
                    "friendly_name": "virtual thingy",
                    "value_template": "{{ True }}",
                    "device_class": "motion",
                }
            },
        }
    }
    assert await setup.async_setup_component(hass, binary_sensor.DOMAIN, config)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test")
    assert state is not None
    assert state.name == "virtual thingy"
    assert state.state == "on"
    assert state.attributes["device_class"] == "motion"


async def test_setup_no_sensors(hass):
    """Test setup with no sensors."""
    assert await setup.async_setup_component(
        hass, binary_sensor.DOMAIN, {"binary_sensor": {"platform": "template"}}
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == 0


async def test_setup_invalid_device(hass):
    """Test the setup with invalid devices."""
    assert await setup.async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {"binary_sensor": {"platform": "template", "sensors": {"foo bar": {}}}},
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == 0


async def test_setup_invalid_device_class(hass):
    """Test setup with invalid sensor class."""
    assert await setup.async_setup_component(
        hass,
        binary_sensor.DOMAIN,
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
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == 0


async def test_setup_invalid_missing_template(hass):
    """Test setup with invalid and missing template."""
    assert await setup.async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {"test": {"device_class": "motion"}},
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == 0


async def test_icon_template(hass):
    """Test icon template."""
    assert await setup.async_setup_component(
        hass,
        binary_sensor.DOMAIN,
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
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_template_sensor")
    assert state.attributes.get("icon") == ""

    hass.states.async_set("binary_sensor.test_state", "Works")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_template_sensor")
    assert state.attributes["icon"] == "mdi:check"


async def test_entity_picture_template(hass):
    """Test entity_picture template."""
    assert await setup.async_setup_component(
        hass,
        binary_sensor.DOMAIN,
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
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_template_sensor")
    assert state.attributes.get("entity_picture") == ""

    hass.states.async_set("binary_sensor.test_state", "Works")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_template_sensor")
    assert state.attributes["entity_picture"] == "/local/sensor.png"


async def test_attribute_templates(hass):
    """Test attribute_templates template."""
    assert await setup.async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor": {
                        "value_template": "{{ states.sensor.xyz.state }}",
                        "attribute_templates": {
                            "test_attribute": "It {{ states.sensor.test_state.state }}."
                        },
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_template_sensor")
    assert state.attributes.get("test_attribute") == "It ."
    hass.states.async_set("sensor.test_state", "Works2")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "Works")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_template_sensor")
    assert state.attributes["test_attribute"] == "It Works."


async def test_match_all(hass):
    """Test template that is rerendered on any state lifecycle."""
    with patch(
        "homeassistant.components.template.binary_sensor."
        "BinarySensorTemplate._update_state"
    ) as _update_state:
        assert await setup.async_setup_component(
            hass,
            binary_sensor.DOMAIN,
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
        )

        await hass.async_start()
        await hass.async_block_till_done()
        init_calls = len(_update_state.mock_calls)

        hass.states.async_set("sensor.any_state", "update")
        await hass.async_block_till_done()
        assert len(_update_state.mock_calls) == init_calls


async def test_event(hass):
    """Test the event."""
    config = {
        "binary_sensor": {
            "platform": "template",
            "sensors": {
                "test": {
                    "friendly_name": "virtual thingy",
                    "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                    "device_class": "motion",
                }
            },
        }
    }
    assert await setup.async_setup_component(hass, binary_sensor.DOMAIN, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"


async def test_template_delay_on(hass):
    """Test binary sensor template delay on."""
    config = {
        "binary_sensor": {
            "platform": "template",
            "sensors": {
                "test": {
                    "friendly_name": "virtual thingy",
                    "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                    "device_class": "motion",
                    "delay_on": 5,
                }
            },
        }
    }
    await setup.async_setup_component(hass, binary_sensor.DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    # check with time changes
    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"


async def test_template_delay_off(hass):
    """Test binary sensor template delay off."""
    config = {
        "binary_sensor": {
            "platform": "template",
            "sensors": {
                "test": {
                    "friendly_name": "virtual thingy",
                    "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                    "device_class": "motion",
                    "delay_off": 5,
                }
            },
        }
    }
    hass.states.async_set("sensor.test_state", "on")
    await setup.async_setup_component(hass, binary_sensor.DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()

    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    # check with time changes
    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"


async def test_template_with_templated_delay_on(hass):
    """Test binary sensor template with template delay on."""
    config = {
        "binary_sensor": {
            "platform": "template",
            "sensors": {
                "test": {
                    "friendly_name": "virtual thingy",
                    "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                    "device_class": "motion",
                    "delay_on": '{{ ({ "seconds": 6 / 2 }) }}',
                }
            },
        }
    }
    await setup.async_setup_component(hass, binary_sensor.DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    future = dt_util.utcnow() + timedelta(seconds=3)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    # check with time changes
    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    future = dt_util.utcnow() + timedelta(seconds=3)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"


async def test_template_with_templated_delay_off(hass):
    """Test binary sensor template with template delay off."""
    config = {
        "binary_sensor": {
            "platform": "template",
            "sensors": {
                "test": {
                    "friendly_name": "virtual thingy",
                    "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                    "device_class": "motion",
                    "delay_off": '{{ ({ "seconds": 6 / 2 }) }}',
                }
            },
        }
    }
    hass.states.async_set("sensor.test_state", "on")
    await setup.async_setup_component(hass, binary_sensor.DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()

    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    future = dt_util.utcnow() + timedelta(seconds=3)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    # check with time changes
    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    future = dt_util.utcnow() + timedelta(seconds=3)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"


async def test_template_with_delay_on_based_on_input(hass):
    """Test binary sensor template with template delay on based on input number."""
    config = {
        "binary_sensor": {
            "platform": "template",
            "sensors": {
                "test": {
                    "friendly_name": "virtual thingy",
                    "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                    "device_class": "motion",
                    "delay_on": '{{ ({ "seconds": states("input_number.delay")|int }) }}',
                }
            },
        }
    }
    await setup.async_setup_component(hass, binary_sensor.DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()

    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    hass.states.async_set("input_number.delay", 3)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    future = dt_util.utcnow() + timedelta(seconds=3)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    # set input to 4 seconds
    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("input_number.delay", 4)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    future = dt_util.utcnow() + timedelta(seconds=2)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    future = dt_util.utcnow() + timedelta(seconds=4)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"


async def test_template_with_delay_off_based_on_input(hass):
    """Test binary sensor template with template delay off based on input number."""
    config = {
        "binary_sensor": {
            "platform": "template",
            "sensors": {
                "test": {
                    "friendly_name": "virtual thingy",
                    "value_template": "{{ states.sensor.test_state.state == 'on' }}",
                    "device_class": "motion",
                    "delay_off": '{{ ({ "seconds": states("input_number.delay")|int }) }}',
                }
            },
        }
    }
    await setup.async_setup_component(hass, binary_sensor.DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    hass.states.async_set("input_number.delay", 3)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    future = dt_util.utcnow() + timedelta(seconds=3)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    # set input to 4 seconds
    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("input_number.delay", 4)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    future = dt_util.utcnow() + timedelta(seconds=2)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    future = dt_util.utcnow() + timedelta(seconds=4)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"


async def test_available_without_availability_template(hass):
    """Ensure availability is true without an availability_template."""
    config = {
        "binary_sensor": {
            "platform": "template",
            "sensors": {
                "test": {
                    "friendly_name": "virtual thingy",
                    "value_template": "true",
                    "device_class": "motion",
                    "delay_off": 5,
                }
            },
        }
    }
    await setup.async_setup_component(hass, binary_sensor.DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")

    assert state.state != STATE_UNAVAILABLE
    assert state.attributes[ATTR_DEVICE_CLASS] == "motion"


async def test_availability_template(hass):
    """Test availability template."""
    config = {
        "binary_sensor": {
            "platform": "template",
            "sensors": {
                "test": {
                    "friendly_name": "virtual thingy",
                    "value_template": "true",
                    "device_class": "motion",
                    "delay_off": 5,
                    "availability_template": "{{ is_state('sensor.test_state','on') }}",
                }
            },
        }
    }
    await setup.async_setup_component(hass, binary_sensor.DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_state", STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.test").state == STATE_UNAVAILABLE

    hass.states.async_set("sensor.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")

    assert state.state != STATE_UNAVAILABLE
    assert state.attributes[ATTR_DEVICE_CLASS] == "motion"


async def test_invalid_attribute_template(hass, caplog):
    """Test that errors are logged if rendering template fails."""
    hass.states.async_set("binary_sensor.test_sensor", "true")

    await setup.async_setup_component(
        hass,
        binary_sensor.DOMAIN,
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
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2
    await hass.async_start()
    await hass.async_block_till_done()

    assert "test_attribute" in caplog.text
    assert "TemplateError" in caplog.text


async def test_invalid_availability_template_keeps_component_available(hass, caplog):
    """Test that an invalid availability keeps the device available."""

    await setup.async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "my_sensor": {
                        "value_template": "{{ states.binary_sensor.test_sensor }}",
                        "availability_template": "{{ x - 12 }}",
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.my_sensor").state != STATE_UNAVAILABLE
    assert ("UndefinedError: 'x' is undefined") in caplog.text


async def test_no_update_template_match_all(hass, caplog):
    """Test that we do not update sensors that match on all."""
    hass.states.async_set("binary_sensor.test_sensor", "true")

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
    assert len(hass.states.async_all()) == 5

    assert hass.states.get("binary_sensor.all_state").state == "off"
    assert hass.states.get("binary_sensor.all_icon").state == "off"
    assert hass.states.get("binary_sensor.all_entity_picture").state == "off"
    assert hass.states.get("binary_sensor.all_attribute").state == "off"

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.all_state").state == "on"
    assert hass.states.get("binary_sensor.all_icon").state == "on"
    assert hass.states.get("binary_sensor.all_entity_picture").state == "on"
    assert hass.states.get("binary_sensor.all_attribute").state == "on"

    hass.states.async_set("binary_sensor.test_sensor", "false")
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.all_state").state == "on"
    # Will now process because we have one valid template
    assert hass.states.get("binary_sensor.all_icon").state == "off"
    assert hass.states.get("binary_sensor.all_entity_picture").state == "off"
    assert hass.states.get("binary_sensor.all_attribute").state == "off"

    await hass.helpers.entity_component.async_update_entity("binary_sensor.all_state")
    await hass.helpers.entity_component.async_update_entity("binary_sensor.all_icon")
    await hass.helpers.entity_component.async_update_entity(
        "binary_sensor.all_entity_picture"
    )
    await hass.helpers.entity_component.async_update_entity(
        "binary_sensor.all_attribute"
    )

    assert hass.states.get("binary_sensor.all_state").state == "on"
    assert hass.states.get("binary_sensor.all_icon").state == "off"
    assert hass.states.get("binary_sensor.all_entity_picture").state == "off"
    assert hass.states.get("binary_sensor.all_attribute").state == "off"


async def test_unique_id(hass):
    """Test unique_id option only creates one binary sensor per id."""
    await setup.async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
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
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1


async def test_template_validation_error(hass, caplog):
    """Test binary sensor template delay on."""
    caplog.set_level(logging.ERROR)
    config = {
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
    }
    await setup.async_setup_component(hass, binary_sensor.DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

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


async def test_trigger_entity(hass):
    """Test trigger entity works."""
    assert await setup.async_setup_component(
        hass,
        "template",
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
                                "plus_one": "{{ trigger.event.data.beer + 1 }}"
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
    )

    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.hello_name")
    assert state is not None
    assert state.state == "off"

    state = hass.states.get("binary_sensor.bare_minimum")
    assert state is not None
    assert state.state == "off"

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 2}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.hello_name")
    assert state.state == "on"
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
    assert state.state == "on"
    assert state.attributes.get("device_class") == "battery"
    assert state.attributes.get("icon") == "mdi:pirate"
    assert state.attributes.get("entity_picture") == "/local/dogs.png"
    assert state.attributes.get("plus_one") == 3
    assert state.context is context


async def test_template_with_trigger_templated_delay_on(hass):
    """Test binary sensor template with template delay on."""
    config = {
        "template": {
            "trigger": {"platform": "event", "event_type": "test_event"},
            "binary_sensor": {
                "name": "test",
                "state": "{{ trigger.event.data.beer == 2 }}",
                "device_class": "motion",
                "delay_on": '{{ ({ "seconds": 6 / 2 }) }}',
            },
        }
    }
    await setup.async_setup_component(hass, "template", config)
    await hass.async_block_till_done()
    await hass.async_start()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 2}, context=context)
    await hass.async_block_till_done()

    future = dt_util.utcnow() + timedelta(seconds=3)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"
