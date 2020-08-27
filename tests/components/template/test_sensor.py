"""The test for the Template sensor platform."""
from asyncio import Event
from unittest.mock import patch

from homeassistant.bootstrap import async_from_config_dict
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import CoreState, callback
from homeassistant.helpers.template import Template
from homeassistant.setup import ATTR_COMPONENT, async_setup_component, setup_component
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component, get_test_home_assistant


class TestTemplateSensor:
    """Test the Template sensor."""

    hass = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_template(self):
        """Test template."""
        with assert_setup_component(1):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {
                            "test_template_sensor": {
                                "value_template": "It {{ states.sensor.test_state.state }}."
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_template_sensor")
        assert state.state == "It ."

        self.hass.states.set("sensor.test_state", "Works")
        self.hass.block_till_done()
        state = self.hass.states.get("sensor.test_template_sensor")
        assert state.state == "It Works."

    def test_icon_template(self):
        """Test icon template."""
        with assert_setup_component(1):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {
                            "test_template_sensor": {
                                "value_template": "{{ states.sensor.test_state.state }}",
                                "icon_template": "{% if states.sensor.test_state.state == "
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

        state = self.hass.states.get("sensor.test_template_sensor")
        assert state.attributes.get("icon") == ""

        self.hass.states.set("sensor.test_state", "Works")
        self.hass.block_till_done()
        state = self.hass.states.get("sensor.test_template_sensor")
        assert state.attributes["icon"] == "mdi:check"

    def test_entity_picture_template(self):
        """Test entity_picture template."""
        with assert_setup_component(1):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {
                            "test_template_sensor": {
                                "value_template": "{{ states.sensor.test_state.state }}",
                                "entity_picture_template": "{% if states.sensor.test_state.state == "
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

        state = self.hass.states.get("sensor.test_template_sensor")
        assert state.attributes.get("entity_picture") == ""

        self.hass.states.set("sensor.test_state", "Works")
        self.hass.block_till_done()
        state = self.hass.states.get("sensor.test_template_sensor")
        assert state.attributes["entity_picture"] == "/local/sensor.png"

    def test_friendly_name_template(self):
        """Test friendly_name template."""
        with assert_setup_component(1):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {
                            "test_template_sensor": {
                                "value_template": "{{ states.sensor.test_state.state }}",
                                "friendly_name_template": "It {{ states.sensor.test_state.state }}.",
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_template_sensor")
        assert state.attributes.get("friendly_name") == "It ."

        self.hass.states.set("sensor.test_state", "Works")
        self.hass.block_till_done()
        state = self.hass.states.get("sensor.test_template_sensor")
        assert state.attributes["friendly_name"] == "It Works."

    def test_friendly_name_template_with_unknown_state(self):
        """Test friendly_name template with an unknown value_template."""
        with assert_setup_component(1):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {
                            "test_template_sensor": {
                                "value_template": "{{ states.fourohfour.state }}",
                                "friendly_name_template": "It {{ states.sensor.test_state.state }}.",
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_template_sensor")
        assert state.attributes["friendly_name"] == "It ."

        self.hass.states.set("sensor.test_state", "Works")
        self.hass.block_till_done()
        state = self.hass.states.get("sensor.test_template_sensor")
        assert state.attributes["friendly_name"] == "It Works."

    def test_attribute_templates(self):
        """Test attribute_templates template."""
        with assert_setup_component(1):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {
                            "test_template_sensor": {
                                "value_template": "{{ states.sensor.test_state.state }}",
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

        state = self.hass.states.get("sensor.test_template_sensor")
        assert state.attributes.get("test_attribute") == "It ."

        self.hass.states.set("sensor.test_state", "Works")
        self.hass.block_till_done()
        state = self.hass.states.get("sensor.test_template_sensor")
        assert state.attributes["test_attribute"] == "It Works."

    def test_template_syntax_error(self):
        """Test templating syntax error."""
        with assert_setup_component(0):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {
                            "test_template_sensor": {
                                "value_template": "{% if rubbish %}"
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()
        assert self.hass.states.all() == []

    def test_template_attribute_missing(self):
        """Test missing attribute template."""
        with assert_setup_component(1):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {
                            "test_template_sensor": {
                                "value_template": "It {{ states.sensor.test_state"
                                ".attributes.missing }}."
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_template_sensor")
        assert state.state == STATE_UNAVAILABLE

    def test_invalid_name_does_not_create(self):
        """Test invalid name."""
        with assert_setup_component(0):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {
                            "test INVALID sensor": {
                                "value_template": "{{ states.sensor.test_state.state }}"
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_invalid_sensor_does_not_create(self):
        """Test invalid sensor."""
        with assert_setup_component(0):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {"test_template_sensor": "invalid"},
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()

        assert self.hass.states.all() == []

    def test_no_sensors_does_not_create(self):
        """Test no sensors."""
        with assert_setup_component(0):
            assert setup_component(
                self.hass, "sensor", {"sensor": {"platform": "template"}}
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_missing_template_does_not_create(self):
        """Test missing template."""
        with assert_setup_component(0):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {
                            "test_template_sensor": {
                                "not_value_template": "{{ states.sensor.test_state.state }}"
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_setup_invalid_device_class(self):
        """Test setup with invalid device_class."""
        with assert_setup_component(0):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {
                            "test": {
                                "value_template": "{{ states.sensor.test_sensor.state }}",
                                "device_class": "foobarnotreal",
                            }
                        },
                    }
                },
            )

    def test_setup_valid_device_class(self):
        """Test setup with valid device_class."""
        with assert_setup_component(1):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {
                            "test1": {
                                "value_template": "{{ states.sensor.test_sensor.state }}",
                                "device_class": "temperature",
                            },
                            "test2": {
                                "value_template": "{{ states.sensor.test_sensor.state }}"
                            },
                        },
                    }
                },
            )
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test1")
        assert state.attributes["device_class"] == "temperature"
        state = self.hass.states.get("sensor.test2")
        assert "device_class" not in state.attributes

    def test_available_template_with_entities(self):
        """Test availability tempalates with values from other entities."""

        with assert_setup_component(1):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": {
                        "platform": "template",
                        "sensors": {
                            "test_template_sensor": {
                                "value_template": "{{ states.sensor.test_state.state }}",
                                "availability_template": "{{ is_state('availability_boolean.state', 'on') }}",
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        # When template returns true..
        self.hass.states.set("availability_boolean.state", STATE_ON)
        self.hass.block_till_done()

        # Device State should not be unavailable
        assert (
            self.hass.states.get("sensor.test_template_sensor").state
            != STATE_UNAVAILABLE
        )

        # When Availability template returns false
        self.hass.states.set("availability_boolean.state", STATE_OFF)
        self.hass.block_till_done()

        # device state should be unavailable
        assert (
            self.hass.states.get("sensor.test_template_sensor").state
            == STATE_UNAVAILABLE
        )


async def test_creating_sensor_loads_group(hass):
    """Test setting up template sensor loads group component first."""
    order = []
    after_dep_event = Event()

    async def async_setup_group(hass, config):
        # Make sure group takes longer to load, so that it won't
        # be loaded first by chance
        await after_dep_event.wait()

        order.append("group")
        return True

    async def async_setup_template(
        hass, config, async_add_entities, discovery_info=None
    ):
        order.append("sensor.template")
        return True

    async def set_after_dep_event(event):
        if event.data[ATTR_COMPONENT] == "sensor":
            after_dep_event.set()

    hass.bus.async_listen(EVENT_COMPONENT_LOADED, set_after_dep_event)

    with patch(
        "homeassistant.components.group.async_setup",
        new=async_setup_group,
    ), patch(
        "homeassistant.components.template.sensor.async_setup_platform",
        new=async_setup_template,
    ):
        await async_from_config_dict(
            {"sensor": {"platform": "template", "sensors": {}}, "group": {}}, hass
        )
        await hass.async_block_till_done()

    assert order == ["group", "sensor.template"]


async def test_available_template_with_entities(hass):
    """Test availability tempalates with values from other entities."""
    hass.states.async_set("sensor.availability_sensor", STATE_OFF)
    with assert_setup_component(1, "sensor"):
        assert await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": {
                    "platform": "template",
                    "sensors": {
                        "test_template_sensor": {
                            "value_template": "{{ states.sensor.test_sensor.state }}",
                            "availability_template": "{{ is_state('sensor.availability_sensor', 'on') }}",
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # When template returns true..
    hass.states.async_set("sensor.availability_sensor", STATE_ON)
    await hass.async_block_till_done()

    # Device State should not be unavailable
    assert hass.states.get("sensor.test_template_sensor").state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set("sensor.availability_sensor", STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert hass.states.get("sensor.test_template_sensor").state == STATE_UNAVAILABLE


async def test_invalid_attribute_template(hass, caplog):
    """Test that errors are logged if rendering template fails."""
    hass.states.async_set("sensor.test_sensor", "startup")

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "invalid_template": {
                        "value_template": "{{ states.sensor.test_sensor.state }}",
                        "attribute_templates": {
                            "test_attribute": "{{ states.sensor.unknown.attributes.picture }}"
                        },
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    await hass.helpers.entity_component.async_update_entity("sensor.invalid_template")

    assert "TemplateError" in caplog.text
    assert "test_attribute" in caplog.text


async def test_invalid_availability_template_keeps_component_available(hass, caplog):
    """Test that an invalid availability keeps the device available."""

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "my_sensor": {
                        "value_template": "{{ states.sensor.test_state.state }}",
                        "availability_template": "{{ x - 12 }}",
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.my_sensor").state != STATE_UNAVAILABLE
    assert ("UndefinedError: 'x' is undefined") in caplog.text


async def test_no_template_match_all(hass, caplog):
    """Test that we allow static templates."""
    hass.states.async_set("sensor.test_sensor", "startup")

    hass.state = CoreState.not_running

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "invalid_state": {"value_template": "{{ 1 + 1 }}"},
                    "invalid_icon": {
                        "value_template": "{{ states.sensor.test_sensor.state }}",
                        "icon_template": "{{ 1 + 1 }}",
                    },
                    "invalid_entity_picture": {
                        "value_template": "{{ states.sensor.test_sensor.state }}",
                        "entity_picture_template": "{{ 1 + 1 }}",
                    },
                    "invalid_friendly_name": {
                        "value_template": "{{ states.sensor.test_sensor.state }}",
                        "friendly_name_template": "{{ 1 + 1 }}",
                    },
                    "invalid_attribute": {
                        "value_template": "{{ states.sensor.test_sensor.state }}",
                        "attribute_templates": {"test_attribute": "{{ 1 + 1 }}"},
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.invalid_state").state == "unknown"
    assert hass.states.get("sensor.invalid_icon").state == "unknown"
    assert hass.states.get("sensor.invalid_entity_picture").state == "unknown"
    assert hass.states.get("sensor.invalid_friendly_name").state == "unknown"

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 6

    assert hass.states.get("sensor.invalid_state").state == "unknown"
    assert hass.states.get("sensor.invalid_icon").state == "unknown"
    assert hass.states.get("sensor.invalid_entity_picture").state == "unknown"
    assert hass.states.get("sensor.invalid_friendly_name").state == "unknown"
    assert hass.states.get("sensor.invalid_attribute").state == "unknown"

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.invalid_state").state == "2"
    assert hass.states.get("sensor.invalid_icon").state == "startup"
    assert hass.states.get("sensor.invalid_entity_picture").state == "startup"
    assert hass.states.get("sensor.invalid_friendly_name").state == "startup"
    assert hass.states.get("sensor.invalid_attribute").state == "startup"

    hass.states.async_set("sensor.test_sensor", "hello")
    await hass.async_block_till_done()

    assert hass.states.get("sensor.invalid_state").state == "2"
    # Will now process because we have at least one valid template
    assert hass.states.get("sensor.invalid_icon").state == "hello"
    assert hass.states.get("sensor.invalid_entity_picture").state == "hello"
    assert hass.states.get("sensor.invalid_friendly_name").state == "hello"
    assert hass.states.get("sensor.invalid_attribute").state == "hello"

    await hass.helpers.entity_component.async_update_entity("sensor.invalid_state")
    await hass.helpers.entity_component.async_update_entity("sensor.invalid_icon")
    await hass.helpers.entity_component.async_update_entity(
        "sensor.invalid_entity_picture"
    )
    await hass.helpers.entity_component.async_update_entity(
        "sensor.invalid_friendly_name"
    )
    await hass.helpers.entity_component.async_update_entity("sensor.invalid_attribute")

    assert hass.states.get("sensor.invalid_state").state == "2"
    assert hass.states.get("sensor.invalid_icon").state == "hello"
    assert hass.states.get("sensor.invalid_entity_picture").state == "hello"
    assert hass.states.get("sensor.invalid_friendly_name").state == "hello"
    assert hass.states.get("sensor.invalid_attribute").state == "hello"


async def test_unique_id(hass):
    """Test unique_id option only creates one sensor per id."""
    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "test_template_sensor_01": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ true }}",
                    },
                    "test_template_sensor_02": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ false }}",
                    },
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1


async def test_sun_renders_once_per_sensor(hass):
    """Test sun change renders the template only once per sensor."""

    now = dt_util.utcnow()
    hass.states.async_set(
        "sun.sun", "above_horizon", {"elevation": 45.3, "next_rising": now}
    )

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "template",
                "sensors": {
                    "solar_angle": {
                        "friendly_name": "Sun angle",
                        "unit_of_measurement": "degrees",
                        "value_template": "{{ state_attr('sun.sun', 'elevation') }}",
                    },
                    "sunrise": {
                        "value_template": "{{ state_attr('sun.sun', 'next_rising') }}"
                    },
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3

    assert hass.states.get("sensor.solar_angle").state == "45.3"
    assert hass.states.get("sensor.sunrise").state == str(now)

    async_render_calls = []

    @callback
    def _record_async_render(self, *args, **kwargs):
        """Catch async_render."""
        async_render_calls.append(self.template)
        return "mocked"

    later = dt_util.utcnow()

    with patch.object(Template, "async_render", _record_async_render):
        hass.states.async_set("sun.sun", {"elevation": 50, "next_rising": later})
        await hass.async_block_till_done()

    assert hass.states.get("sensor.solar_angle").state == "mocked"
    assert hass.states.get("sensor.sunrise").state == "mocked"

    assert len(async_render_calls) == 2
    assert set(async_render_calls) == {
        "{{ state_attr('sun.sun', 'elevation') }}",
        "{{ state_attr('sun.sun', 'next_rising') }}",
    }
