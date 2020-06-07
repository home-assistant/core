"""The tests for the  Template switch platform."""
from homeassistant import setup
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import callback

from tests.common import assert_setup_component, get_test_home_assistant
from tests.components.switch import common


class TestTemplateSwitch:
    """Test the Template switch."""

    hass = None
    calls = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.calls = []

        @callback
        def record_call(service):
            """Track function calls.."""
            self.calls.append(service)

        self.hass.services.register("test", "automation", record_call)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_template_state_text(self):
        """Test the state text of a template."""
        with assert_setup_component(1, "switch"):
            assert setup.setup_component(
                self.hass,
                "switch",
                {
                    "switch": {
                        "platform": "template",
                        "switches": {
                            "test_template_switch": {
                                "value_template": "{{ states.switch.test_state.state }}",
                                "turn_on": {
                                    "service": "switch.turn_on",
                                    "entity_id": "switch.test_state",
                                },
                                "turn_off": {
                                    "service": "switch.turn_off",
                                    "entity_id": "switch.test_state",
                                },
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.set("switch.test_state", STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get("switch.test_template_switch")
        assert state.state == STATE_ON

        state = self.hass.states.set("switch.test_state", STATE_OFF)
        self.hass.block_till_done()

        state = self.hass.states.get("switch.test_template_switch")
        assert state.state == STATE_OFF

    def test_template_state_boolean_on(self):
        """Test the setting of the state with boolean on."""
        with assert_setup_component(1, "switch"):
            assert setup.setup_component(
                self.hass,
                "switch",
                {
                    "switch": {
                        "platform": "template",
                        "switches": {
                            "test_template_switch": {
                                "value_template": "{{ 1 == 1 }}",
                                "turn_on": {
                                    "service": "switch.turn_on",
                                    "entity_id": "switch.test_state",
                                },
                                "turn_off": {
                                    "service": "switch.turn_off",
                                    "entity_id": "switch.test_state",
                                },
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("switch.test_template_switch")
        assert state.state == STATE_ON

    def test_template_state_boolean_off(self):
        """Test the setting of the state with off."""
        with assert_setup_component(1, "switch"):
            assert setup.setup_component(
                self.hass,
                "switch",
                {
                    "switch": {
                        "platform": "template",
                        "switches": {
                            "test_template_switch": {
                                "value_template": "{{ 1 == 2 }}",
                                "turn_on": {
                                    "service": "switch.turn_on",
                                    "entity_id": "switch.test_state",
                                },
                                "turn_off": {
                                    "service": "switch.turn_off",
                                    "entity_id": "switch.test_state",
                                },
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("switch.test_template_switch")
        assert state.state == STATE_OFF

    def test_icon_template(self):
        """Test icon template."""
        with assert_setup_component(1, "switch"):
            assert setup.setup_component(
                self.hass,
                "switch",
                {
                    "switch": {
                        "platform": "template",
                        "switches": {
                            "test_template_switch": {
                                "value_template": "{{ states.switch.test_state.state }}",
                                "turn_on": {
                                    "service": "switch.turn_on",
                                    "entity_id": "switch.test_state",
                                },
                                "turn_off": {
                                    "service": "switch.turn_off",
                                    "entity_id": "switch.test_state",
                                },
                                "icon_template": "{% if states.switch.test_state.state %}"
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

        state = self.hass.states.get("switch.test_template_switch")
        assert state.attributes.get("icon") == ""

        state = self.hass.states.set("switch.test_state", STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get("switch.test_template_switch")
        assert state.attributes["icon"] == "mdi:check"

    def test_entity_picture_template(self):
        """Test entity_picture template."""
        with assert_setup_component(1, "switch"):
            assert setup.setup_component(
                self.hass,
                "switch",
                {
                    "switch": {
                        "platform": "template",
                        "switches": {
                            "test_template_switch": {
                                "value_template": "{{ states.switch.test_state.state }}",
                                "turn_on": {
                                    "service": "switch.turn_on",
                                    "entity_id": "switch.test_state",
                                },
                                "turn_off": {
                                    "service": "switch.turn_off",
                                    "entity_id": "switch.test_state",
                                },
                                "entity_picture_template": "{% if states.switch.test_state.state %}"
                                "/local/switch.png"
                                "{% endif %}",
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("switch.test_template_switch")
        assert state.attributes.get("entity_picture") == ""

        state = self.hass.states.set("switch.test_state", STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get("switch.test_template_switch")
        assert state.attributes["entity_picture"] == "/local/switch.png"

    def test_template_syntax_error(self):
        """Test templating syntax error."""
        with assert_setup_component(0, "switch"):
            assert setup.setup_component(
                self.hass,
                "switch",
                {
                    "switch": {
                        "platform": "template",
                        "switches": {
                            "test_template_switch": {
                                "value_template": "{% if rubbish %}",
                                "turn_on": {
                                    "service": "switch.turn_on",
                                    "entity_id": "switch.test_state",
                                },
                                "turn_off": {
                                    "service": "switch.turn_off",
                                    "entity_id": "switch.test_state",
                                },
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_invalid_name_does_not_create(self):
        """Test invalid name."""
        with assert_setup_component(0, "switch"):
            assert setup.setup_component(
                self.hass,
                "switch",
                {
                    "switch": {
                        "platform": "template",
                        "switches": {
                            "test INVALID switch": {
                                "value_template": "{{ rubbish }",
                                "turn_on": {
                                    "service": "switch.turn_on",
                                    "entity_id": "switch.test_state",
                                },
                                "turn_off": {
                                    "service": "switch.turn_off",
                                    "entity_id": "switch.test_state",
                                },
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_invalid_switch_does_not_create(self):
        """Test invalid switch."""
        with assert_setup_component(0, "switch"):
            assert setup.setup_component(
                self.hass,
                "switch",
                {
                    "switch": {
                        "platform": "template",
                        "switches": {"test_template_switch": "Invalid"},
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_no_switches_does_not_create(self):
        """Test if there are no switches no creation."""
        with assert_setup_component(0, "switch"):
            assert setup.setup_component(
                self.hass, "switch", {"switch": {"platform": "template"}}
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_missing_template_does_not_create(self):
        """Test missing template."""
        with assert_setup_component(0, "switch"):
            assert setup.setup_component(
                self.hass,
                "switch",
                {
                    "switch": {
                        "platform": "template",
                        "switches": {
                            "test_template_switch": {
                                "not_value_template": "{{ states.switch.test_state.state }}",
                                "turn_on": {
                                    "service": "switch.turn_on",
                                    "entity_id": "switch.test_state",
                                },
                                "turn_off": {
                                    "service": "switch.turn_off",
                                    "entity_id": "switch.test_state",
                                },
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_missing_on_does_not_create(self):
        """Test missing on."""
        with assert_setup_component(0, "switch"):
            assert setup.setup_component(
                self.hass,
                "switch",
                {
                    "switch": {
                        "platform": "template",
                        "switches": {
                            "test_template_switch": {
                                "value_template": "{{ states.switch.test_state.state }}",
                                "not_on": {
                                    "service": "switch.turn_on",
                                    "entity_id": "switch.test_state",
                                },
                                "turn_off": {
                                    "service": "switch.turn_off",
                                    "entity_id": "switch.test_state",
                                },
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_missing_off_does_not_create(self):
        """Test missing off."""
        with assert_setup_component(0, "switch"):
            assert setup.setup_component(
                self.hass,
                "switch",
                {
                    "switch": {
                        "platform": "template",
                        "switches": {
                            "test_template_switch": {
                                "value_template": "{{ states.switch.test_state.state }}",
                                "turn_on": {
                                    "service": "switch.turn_on",
                                    "entity_id": "switch.test_state",
                                },
                                "not_off": {
                                    "service": "switch.turn_off",
                                    "entity_id": "switch.test_state",
                                },
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_on_action(self):
        """Test on action."""
        assert setup.setup_component(
            self.hass,
            "switch",
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        "test_template_switch": {
                            "value_template": "{{ states.switch.test_state.state }}",
                            "turn_on": {"service": "test.automation"},
                            "turn_off": {
                                "service": "switch.turn_off",
                                "entity_id": "switch.test_state",
                            },
                        }
                    },
                }
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set("switch.test_state", STATE_OFF)
        self.hass.block_till_done()

        state = self.hass.states.get("switch.test_template_switch")
        assert state.state == STATE_OFF

        common.turn_on(self.hass, "switch.test_template_switch")
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_off_action(self):
        """Test off action."""
        assert setup.setup_component(
            self.hass,
            "switch",
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        "test_template_switch": {
                            "value_template": "{{ states.switch.test_state.state }}",
                            "turn_on": {
                                "service": "switch.turn_on",
                                "entity_id": "switch.test_state",
                            },
                            "turn_off": {"service": "test.automation"},
                        }
                    },
                }
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set("switch.test_state", STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get("switch.test_template_switch")
        assert state.state == STATE_ON

        common.turn_off(self.hass, "switch.test_template_switch")
        self.hass.block_till_done()

        assert len(self.calls) == 1


async def test_available_template_with_entities(hass):
    """Test availability templates with values from other entities."""
    await setup.async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    "test_template_switch": {
                        "value_template": "{{ 1 == 1 }}",
                        "turn_on": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "turn_off": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                        "availability_template": "{{ is_state('availability_state.state', 'on') }}",
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("availability_state.state", STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_template_switch").state != STATE_UNAVAILABLE

    hass.states.async_set("availability_state.state", STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_template_switch").state == STATE_UNAVAILABLE


async def test_invalid_availability_template_keeps_component_available(hass, caplog):
    """Test that an invalid availability keeps the device available."""
    await setup.async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    "test_template_switch": {
                        "value_template": "{{ true }}",
                        "turn_on": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "turn_off": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                        "availability_template": "{{ x - 12 }}",
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_template_switch").state != STATE_UNAVAILABLE
    assert ("UndefinedError: 'x' is undefined") in caplog.text
