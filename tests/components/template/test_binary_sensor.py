"""The tests for the Template Binary sensor platform."""
from datetime import timedelta
import logging
import unittest
from unittest import mock

from homeassistant import setup
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import CoreState
import homeassistant.util.dt as dt_util

from tests.common import (
    assert_setup_component,
    async_fire_time_changed,
    get_test_home_assistant,
)


class TestBinarySensorTemplate(unittest.TestCase):
    """Test for Binary sensor template platform."""

    hass = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test the setup."""
        config = {
            "binary_sensor": {
                "platform": "template",
                "sensors": {
                    "test": {
                        "friendly_name": "virtual thingy",
                        "value_template": "{{ foo }}",
                        "device_class": "motion",
                    }
                },
            }
        }
        with assert_setup_component(1):
            assert setup.setup_component(self.hass, "binary_sensor", config)

    def test_setup_no_sensors(self):
        """Test setup with no sensors."""
        with assert_setup_component(0):
            assert setup.setup_component(
                self.hass, "binary_sensor", {"binary_sensor": {"platform": "template"}}
            )

    def test_setup_invalid_device(self):
        """Test the setup with invalid devices."""
        with assert_setup_component(0):
            assert setup.setup_component(
                self.hass,
                "binary_sensor",
                {"binary_sensor": {"platform": "template", "sensors": {"foo bar": {}}}},
            )

    def test_setup_invalid_device_class(self):
        """Test setup with invalid sensor class."""
        with assert_setup_component(0):
            assert setup.setup_component(
                self.hass,
                "binary_sensor",
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

    def test_setup_invalid_missing_template(self):
        """Test setup with invalid and missing template."""
        with assert_setup_component(0):
            assert setup.setup_component(
                self.hass,
                "binary_sensor",
                {
                    "binary_sensor": {
                        "platform": "template",
                        "sensors": {"test": {"device_class": "motion"}},
                    }
                },
            )

    def test_icon_template(self):
        """Test icon template."""
        with assert_setup_component(1):
            assert setup.setup_component(
                self.hass,
                "binary_sensor",
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

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_template_sensor")
        assert state.attributes.get("icon") == ""

        self.hass.states.set("binary_sensor.test_state", "Works")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_template_sensor")
        assert state.attributes["icon"] == "mdi:check"

    def test_entity_picture_template(self):
        """Test entity_picture template."""
        with assert_setup_component(1):
            assert setup.setup_component(
                self.hass,
                "binary_sensor",
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

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_template_sensor")
        assert state.attributes.get("entity_picture") == ""

        self.hass.states.set("binary_sensor.test_state", "Works")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_template_sensor")
        assert state.attributes["entity_picture"] == "/local/sensor.png"

    def test_attribute_templates(self):
        """Test attribute_templates template."""
        with assert_setup_component(1):
            assert setup.setup_component(
                self.hass,
                "binary_sensor",
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

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_template_sensor")
        assert state.attributes.get("test_attribute") == "It ."
        self.hass.states.set("sensor.test_state", "Works2")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "Works")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_template_sensor")
        assert state.attributes["test_attribute"] == "It Works."

    @mock.patch(
        "homeassistant.components.template.binary_sensor."
        "BinarySensorTemplate._update_state"
    )
    def test_match_all(self, _update_state):
        """Test template that is rerendered on any state lifecycle."""
        with assert_setup_component(1):
            assert setup.setup_component(
                self.hass,
                "binary_sensor",
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

        self.hass.start()
        self.hass.block_till_done()
        init_calls = len(_update_state.mock_calls)

        self.hass.states.set("sensor.any_state", "update")
        self.hass.block_till_done()
        assert len(_update_state.mock_calls) == init_calls

    def test_event(self):
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
        with assert_setup_component(1):
            assert setup.setup_component(self.hass, "binary_sensor", config)

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test")
        assert state.state == "off"

        self.hass.states.set("sensor.test_state", "on")
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test")
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
    await setup.async_setup_component(hass, "binary_sensor", config)
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
    await setup.async_setup_component(hass, "binary_sensor", config)
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
    await setup.async_setup_component(hass, "binary_sensor", config)
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
    await setup.async_setup_component(hass, "binary_sensor", config)
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
        "binary_sensor",
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
        "binary_sensor",
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
        "binary_sensor",
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
        "binary_sensor",
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
    await setup.async_setup_component(hass, "binary_sensor", config)
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
