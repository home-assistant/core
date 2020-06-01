"""The tests for the Template Binary sensor platform."""
from datetime import timedelta
import unittest
from unittest import mock

from homeassistant import setup
from homeassistant.components.template import binary_sensor as template
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    MATCH_ALL,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template as template_hlpr
from homeassistant.util.async_ import run_callback_threadsafe
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

        self.hass.states.set("sensor.test_state", "Works")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_template_sensor")
        assert state.attributes["test_attribute"] == "It Works."

    @mock.patch(
        "homeassistant.components.template.binary_sensor."
        "BinarySensorTemplate._async_render"
    )
    def test_match_all(self, _async_render):
        """Test MATCH_ALL in template."""
        with assert_setup_component(1):
            assert setup.setup_component(
                self.hass,
                "binary_sensor",
                {
                    "binary_sensor": {
                        "platform": "template",
                        "sensors": {
                            "match_all_template_sensor": {"value_template": "{{ 42 }}"}
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()
        init_calls = len(_async_render.mock_calls)

        self.hass.states.set("sensor.any_state", "update")
        self.hass.block_till_done()
        assert len(_async_render.mock_calls) == init_calls

    def test_attributes(self):
        """Test the attributes."""
        vs = run_callback_threadsafe(
            self.hass.loop,
            template.BinarySensorTemplate,
            self.hass,
            "parent",
            "Parent",
            "motion",
            template_hlpr.Template("{{ 1 > 1 }}", self.hass),
            None,
            None,
            None,
            MATCH_ALL,
            None,
            None,
            None,
        ).result()
        assert not vs.should_poll
        assert "motion" == vs.device_class
        assert "Parent" == vs.name

        run_callback_threadsafe(self.hass.loop, vs.async_check_state).result()
        assert not vs.is_on

        # pylint: disable=protected-access
        vs._template = template_hlpr.Template("{{ 2 > 1 }}", self.hass)

        run_callback_threadsafe(self.hass.loop, vs.async_check_state).result()
        assert vs.is_on

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

    @mock.patch("homeassistant.helpers.template.Template.render")
    def test_update_template_error(self, mock_render):
        """Test the template update error."""
        vs = run_callback_threadsafe(
            self.hass.loop,
            template.BinarySensorTemplate,
            self.hass,
            "parent",
            "Parent",
            "motion",
            template_hlpr.Template("{{ 1 > 1 }}", self.hass),
            None,
            None,
            None,
            MATCH_ALL,
            None,
            None,
            None,
        ).result()
        mock_render.side_effect = TemplateError("foo")
        run_callback_threadsafe(self.hass.loop, vs.async_check_state).result()
        mock_render.side_effect = TemplateError(
            "UndefinedError: 'None' has no attribute"
        )
        run_callback_threadsafe(self.hass.loop, vs.async_check_state).result()


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

    assert hass.states.get("binary_sensor.test").state != STATE_UNAVAILABLE


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

    assert hass.states.get("binary_sensor.test").state != STATE_UNAVAILABLE


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
    await hass.helpers.entity_component.async_update_entity(
        "binary_sensor.invalid_template"
    )

    assert ("Error rendering attribute test_attribute") in caplog.text


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
    assert (
        "Template binary sensor 'all_state' has no entity ids "
        "configured to track nor were we able to extract the entities to "
        "track from the value template"
    ) in caplog.text
    assert (
        "Template binary sensor 'all_icon' has no entity ids "
        "configured to track nor were we able to extract the entities to "
        "track from the icon template"
    ) in caplog.text
    assert (
        "Template binary sensor 'all_entity_picture' has no entity ids "
        "configured to track nor were we able to extract the entities to "
        "track from the entity_picture template"
    ) in caplog.text
    assert (
        "Template binary sensor 'all_attribute' has no entity ids "
        "configured to track nor were we able to extract the entities to "
        "track from the test_attribute template"
    ) in caplog.text

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
    assert hass.states.get("binary_sensor.all_icon").state == "on"
    assert hass.states.get("binary_sensor.all_entity_picture").state == "on"
    assert hass.states.get("binary_sensor.all_attribute").state == "on"

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
