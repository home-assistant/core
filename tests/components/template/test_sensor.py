"""The test for the Template sensor platform."""
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.setup import async_setup_component, setup_component

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
    await hass.helpers.entity_component.async_update_entity("sensor.invalid_template")

    assert ("Error rendering attribute test_attribute") in caplog.text


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
    """Test that we do not allow sensors that match on all."""
    hass.states.async_set("sensor.test_sensor", "startup")

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
    assert (
        "Template sensor 'invalid_state' has no entity ids "
        "configured to track nor were we able to extract the entities to "
        "track from the value template"
    ) in caplog.text
    assert (
        "Template sensor 'invalid_icon' has no entity ids "
        "configured to track nor were we able to extract the entities to "
        "track from the icon template"
    ) in caplog.text
    assert (
        "Template sensor 'invalid_entity_picture' has no entity ids "
        "configured to track nor were we able to extract the entities to "
        "track from the entity_picture template"
    ) in caplog.text
    assert (
        "Template sensor 'invalid_friendly_name' has no entity ids "
        "configured to track nor were we able to extract the entities to "
        "track from the friendly_name template"
    ) in caplog.text
    assert (
        "Template sensor 'invalid_attribute' has no entity ids "
        "configured to track nor were we able to extract the entities to "
        "track from the test_attribute template"
    ) in caplog.text

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
    assert hass.states.get("sensor.invalid_icon").state == "startup"
    assert hass.states.get("sensor.invalid_entity_picture").state == "startup"
    assert hass.states.get("sensor.invalid_friendly_name").state == "startup"
    assert hass.states.get("sensor.invalid_attribute").state == "startup"

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
