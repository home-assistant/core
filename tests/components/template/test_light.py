"""The tests for the  Template light platform."""
import logging

import pytest

from homeassistant import setup
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import callback

from tests.common import assert_setup_component, get_test_home_assistant
from tests.components.light import common

_LOGGER = logging.getLogger(__name__)

# Represent for light's availability
_STATE_AVAILABILITY_BOOLEAN = "availability_boolean.state"


class TestTemplateLight:
    """Test the Template light."""

    hass = None
    calls = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.calls = []

        @callback
        def record_call(service):
            """Track function calls."""
            self.calls.append(service)

        self.hass.services.register("test", "automation", record_call)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_template_state_invalid(self):
        """Test template state with render error."""
        with assert_setup_component(1, "light"):
            assert setup.setup_component(
                self.hass,
                "light",
                {
                    "light": {
                        "platform": "template",
                        "lights": {
                            "test_template_light": {
                                "value_template": "{{states.test['big.fat...']}}",
                                "turn_on": {
                                    "service": "light.turn_on",
                                    "entity_id": "light.test_state",
                                },
                                "turn_off": {
                                    "service": "light.turn_off",
                                    "entity_id": "light.test_state",
                                },
                                "set_level": {
                                    "service": "light.turn_on",
                                    "data_template": {
                                        "entity_id": "light.test_state",
                                        "brightness": "{{brightness}}",
                                    },
                                },
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state.state == STATE_OFF

    def test_template_state_text(self):
        """Test the state text of a template."""
        with assert_setup_component(1, "light"):
            assert setup.setup_component(
                self.hass,
                "light",
                {
                    "light": {
                        "platform": "template",
                        "lights": {
                            "test_template_light": {
                                "value_template": "{{ states.light.test_state.state }}",
                                "turn_on": {
                                    "service": "light.turn_on",
                                    "entity_id": "light.test_state",
                                },
                                "turn_off": {
                                    "service": "light.turn_off",
                                    "entity_id": "light.test_state",
                                },
                                "set_level": {
                                    "service": "light.turn_on",
                                    "data_template": {
                                        "entity_id": "light.test_state",
                                        "brightness": "{{brightness}}",
                                    },
                                },
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.set("light.test_state", STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state.state == STATE_ON

        state = self.hass.states.set("light.test_state", STATE_OFF)
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state.state == STATE_OFF

    @pytest.mark.parametrize(
        "expected_state,template",
        [(STATE_ON, "{{ 1 == 1 }}"), (STATE_OFF, "{{ 1 == 2 }}")],
    )
    def test_template_state_boolean(self, expected_state, template):
        """Test the setting of the state with boolean on."""
        with assert_setup_component(1, "light"):
            assert setup.setup_component(
                self.hass,
                "light",
                {
                    "light": {
                        "platform": "template",
                        "lights": {
                            "test_template_light": {
                                "value_template": template,
                                "turn_on": {
                                    "service": "light.turn_on",
                                    "entity_id": "light.test_state",
                                },
                                "turn_off": {
                                    "service": "light.turn_off",
                                    "entity_id": "light.test_state",
                                },
                                "set_level": {
                                    "service": "light.turn_on",
                                    "data_template": {
                                        "entity_id": "light.test_state",
                                        "brightness": "{{brightness}}",
                                    },
                                },
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state.state == expected_state

    def test_template_syntax_error(self):
        """Test templating syntax error."""
        with assert_setup_component(0, "light"):
            assert setup.setup_component(
                self.hass,
                "light",
                {
                    "light": {
                        "platform": "template",
                        "lights": {
                            "test_template_light": {
                                "value_template": "{%- if false -%}",
                                "turn_on": {
                                    "service": "light.turn_on",
                                    "entity_id": "light.test_state",
                                },
                                "turn_off": {
                                    "service": "light.turn_off",
                                    "entity_id": "light.test_state",
                                },
                                "set_level": {
                                    "service": "light.turn_on",
                                    "data_template": {
                                        "entity_id": "light.test_state",
                                        "brightness": "{{brightness}}",
                                    },
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
        with assert_setup_component(0, "light"):
            assert setup.setup_component(
                self.hass,
                "light",
                {
                    "light": {
                        "platform": "template",
                        "lights": {
                            "bad name here": {
                                "value_template": "{{ 1== 1}}",
                                "turn_on": {
                                    "service": "light.turn_on",
                                    "entity_id": "light.test_state",
                                },
                                "turn_off": {
                                    "service": "light.turn_off",
                                    "entity_id": "light.test_state",
                                },
                                "set_level": {
                                    "service": "light.turn_on",
                                    "data_template": {
                                        "entity_id": "light.test_state",
                                        "brightness": "{{brightness}}",
                                    },
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

    def test_invalid_light_does_not_create(self):
        """Test invalid light."""
        with assert_setup_component(0, "light"):
            assert setup.setup_component(
                self.hass,
                "light",
                {
                    "light": {
                        "platform": "template",
                        "switches": {"test_template_light": "Invalid"},
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_no_lights_does_not_create(self):
        """Test if there are no lights no creation."""
        with assert_setup_component(0, "light"):
            assert setup.setup_component(
                self.hass, "light", {"light": {"platform": "template"}}
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    @pytest.mark.parametrize(
        "missing_key, count", [("value_template", 1), ("turn_on", 0), ("turn_off", 0)]
    )
    def test_missing_key(self, missing_key, count):
        """Test missing template."""
        light = {
            "light": {
                "platform": "template",
                "lights": {
                    "light_one": {
                        "value_template": "{{ 1== 1}}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        }

        del light["light"]["lights"]["light_one"][missing_key]
        with assert_setup_component(count, "light"):
            assert setup.setup_component(self.hass, "light", light)
        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        if count:
            assert self.hass.states.all() != []
        else:
            assert self.hass.states.all() == []

    def test_on_action(self):
        """Test on action."""
        assert setup.setup_component(
            self.hass,
            "light",
            {
                "light": {
                    "platform": "template",
                    "lights": {
                        "test_template_light": {
                            "value_template": "{{states.light.test_state.state}}",
                            "turn_on": {"service": "test.automation"},
                            "turn_off": {
                                "service": "light.turn_off",
                                "entity_id": "light.test_state",
                            },
                            "set_level": {
                                "service": "light.turn_on",
                                "data_template": {
                                    "entity_id": "light.test_state",
                                    "brightness": "{{brightness}}",
                                },
                            },
                        }
                    },
                }
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set("light.test_state", STATE_OFF)
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state.state == STATE_OFF

        common.turn_on(self.hass, "light.test_template_light")
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_on_action_optimistic(self):
        """Test on action with optimistic state."""
        assert setup.setup_component(
            self.hass,
            "light",
            {
                "light": {
                    "platform": "template",
                    "lights": {
                        "test_template_light": {
                            "turn_on": {"service": "test.automation"},
                            "turn_off": {
                                "service": "light.turn_off",
                                "entity_id": "light.test_state",
                            },
                            "set_level": {
                                "service": "light.turn_on",
                                "data_template": {
                                    "entity_id": "light.test_state",
                                    "brightness": "{{brightness}}",
                                },
                            },
                        }
                    },
                }
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set("light.test_state", STATE_OFF)
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state.state == STATE_OFF

        common.turn_on(self.hass, "light.test_template_light")
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert len(self.calls) == 1
        assert state.state == STATE_ON

    def test_off_action(self):
        """Test off action."""
        assert setup.setup_component(
            self.hass,
            "light",
            {
                "light": {
                    "platform": "template",
                    "lights": {
                        "test_template_light": {
                            "value_template": "{{states.light.test_state.state}}",
                            "turn_on": {
                                "service": "light.turn_on",
                                "entity_id": "light.test_state",
                            },
                            "turn_off": {"service": "test.automation"},
                            "set_level": {
                                "service": "light.turn_on",
                                "data_template": {
                                    "entity_id": "light.test_state",
                                    "brightness": "{{brightness}}",
                                },
                            },
                        }
                    },
                }
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set("light.test_state", STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state.state == STATE_ON

        common.turn_off(self.hass, "light.test_template_light")
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_off_action_optimistic(self):
        """Test off action with optimistic state."""
        assert setup.setup_component(
            self.hass,
            "light",
            {
                "light": {
                    "platform": "template",
                    "lights": {
                        "test_template_light": {
                            "turn_on": {
                                "service": "light.turn_on",
                                "entity_id": "light.test_state",
                            },
                            "turn_off": {"service": "test.automation"},
                            "set_level": {
                                "service": "light.turn_on",
                                "data_template": {
                                    "entity_id": "light.test_state",
                                    "brightness": "{{brightness}}",
                                },
                            },
                        }
                    },
                }
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state.state == STATE_OFF

        common.turn_off(self.hass, "light.test_template_light")
        self.hass.block_till_done()

        assert len(self.calls) == 1
        state = self.hass.states.get("light.test_template_light")
        assert state.state == STATE_OFF

    def test_white_value_action_no_template(self):
        """Test setting white value with optimistic template."""
        assert setup.setup_component(
            self.hass,
            "light",
            {
                "light": {
                    "platform": "template",
                    "lights": {
                        "test_template_light": {
                            "value_template": "{{1 == 1}}",
                            "turn_on": {
                                "service": "light.turn_on",
                                "entity_id": "light.test_state",
                            },
                            "turn_off": {
                                "service": "light.turn_off",
                                "entity_id": "light.test_state",
                            },
                            "set_white_value": {
                                "service": "test.automation",
                                "data_template": {
                                    "entity_id": "test.test_state",
                                    "white_value": "{{white_value}}",
                                },
                            },
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state.attributes.get("white_value") is None

        common.turn_on(
            self.hass, "light.test_template_light", **{ATTR_WHITE_VALUE: 124}
        )
        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0].data["white_value"] == "124"

        state = self.hass.states.get("light.test_template_light")
        assert state is not None
        assert state.attributes.get("white_value") == 124

    @pytest.mark.parametrize(
        "expected_white_value,template",
        [
            (255, "{{255}}"),
            (None, "{{256}}"),
            (None, "{{x - 12}}"),
            (None, "{{ none }}"),
            (None, ""),
        ],
    )
    def test_white_value_template(self, expected_white_value, template):
        """Test the template for the white value."""
        with assert_setup_component(1, "light"):
            assert setup.setup_component(
                self.hass,
                "light",
                {
                    "light": {
                        "platform": "template",
                        "lights": {
                            "test_template_light": {
                                "value_template": "{{ 1 == 1 }}",
                                "turn_on": {
                                    "service": "light.turn_on",
                                    "entity_id": "light.test_state",
                                },
                                "turn_off": {
                                    "service": "light.turn_off",
                                    "entity_id": "light.test_state",
                                },
                                "set_white_value": {
                                    "service": "light.turn_on",
                                    "data_template": {
                                        "entity_id": "light.test_state",
                                        "white_value": "{{white_value}}",
                                    },
                                },
                                "white_value_template": template,
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state is not None
        assert state.attributes.get("white_value") == expected_white_value

    def test_level_action_no_template(self):
        """Test setting brightness with optimistic template."""
        assert setup.setup_component(
            self.hass,
            "light",
            {
                "light": {
                    "platform": "template",
                    "lights": {
                        "test_template_light": {
                            "value_template": "{{1 == 1}}",
                            "turn_on": {
                                "service": "light.turn_on",
                                "entity_id": "light.test_state",
                            },
                            "turn_off": {
                                "service": "light.turn_off",
                                "entity_id": "light.test_state",
                            },
                            "set_level": {
                                "service": "test.automation",
                                "data_template": {
                                    "entity_id": "test.test_state",
                                    "brightness": "{{brightness}}",
                                },
                            },
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state.attributes.get("brightness") is None

        common.turn_on(self.hass, "light.test_template_light", **{ATTR_BRIGHTNESS: 124})
        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0].data["brightness"] == "124"

        state = self.hass.states.get("light.test_template_light")
        _LOGGER.info(str(state.attributes))
        assert state is not None
        assert state.attributes.get("brightness") == 124

    @pytest.mark.parametrize(
        "expected_level,template",
        [
            (255, "{{255}}"),
            (None, "{{256}}"),
            (None, "{{x - 12}}"),
            (None, "{{ none }}"),
            (None, ""),
        ],
    )
    def test_level_template(self, expected_level, template):
        """Test the template for the level."""
        with assert_setup_component(1, "light"):
            assert setup.setup_component(
                self.hass,
                "light",
                {
                    "light": {
                        "platform": "template",
                        "lights": {
                            "test_template_light": {
                                "value_template": "{{ 1 == 1 }}",
                                "turn_on": {
                                    "service": "light.turn_on",
                                    "entity_id": "light.test_state",
                                },
                                "turn_off": {
                                    "service": "light.turn_off",
                                    "entity_id": "light.test_state",
                                },
                                "set_level": {
                                    "service": "light.turn_on",
                                    "data_template": {
                                        "entity_id": "light.test_state",
                                        "brightness": "{{brightness}}",
                                    },
                                },
                                "level_template": template,
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state is not None
        assert state.attributes.get("brightness") == expected_level

    @pytest.mark.parametrize(
        "expected_temp,template",
        [
            (500, "{{500}}"),
            (None, "{{501}}"),
            (None, "{{x - 12}}"),
            (None, "None"),
            (None, "{{ none }}"),
            (None, ""),
        ],
    )
    def test_temperature_template(self, expected_temp, template):
        """Test the template for the temperature."""
        with assert_setup_component(1, "light"):
            assert setup.setup_component(
                self.hass,
                "light",
                {
                    "light": {
                        "platform": "template",
                        "lights": {
                            "test_template_light": {
                                "value_template": "{{ 1 == 1 }}",
                                "turn_on": {
                                    "service": "light.turn_on",
                                    "entity_id": "light.test_state",
                                },
                                "turn_off": {
                                    "service": "light.turn_off",
                                    "entity_id": "light.test_state",
                                },
                                "set_temperature": {
                                    "service": "light.turn_on",
                                    "data_template": {
                                        "entity_id": "light.test_state",
                                        "color_temp": "{{color_temp}}",
                                    },
                                },
                                "temperature_template": template,
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state is not None
        assert state.attributes.get("color_temp") == expected_temp

    def test_temperature_action_no_template(self):
        """Test setting temperature with optimistic template."""
        assert setup.setup_component(
            self.hass,
            "light",
            {
                "light": {
                    "platform": "template",
                    "lights": {
                        "test_template_light": {
                            "value_template": "{{1 == 1}}",
                            "turn_on": {
                                "service": "light.turn_on",
                                "entity_id": "light.test_state",
                            },
                            "turn_off": {
                                "service": "light.turn_off",
                                "entity_id": "light.test_state",
                            },
                            "set_temperature": {
                                "service": "test.automation",
                                "data_template": {
                                    "entity_id": "test.test_state",
                                    "color_temp": "{{color_temp}}",
                                },
                            },
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state.attributes.get("color_template") is None

        common.turn_on(self.hass, "light.test_template_light", **{ATTR_COLOR_TEMP: 345})
        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0].data["color_temp"] == "345"

        state = self.hass.states.get("light.test_template_light")
        _LOGGER.info(str(state.attributes))
        assert state is not None
        assert state.attributes.get("color_temp") == 345

    def test_friendly_name(self):
        """Test the accessibility of the friendly_name attribute."""
        with assert_setup_component(1, "light"):
            assert setup.setup_component(
                self.hass,
                "light",
                {
                    "light": {
                        "platform": "template",
                        "lights": {
                            "test_template_light": {
                                "friendly_name": "Template light",
                                "value_template": "{{ 1 == 1 }}",
                                "turn_on": {
                                    "service": "light.turn_on",
                                    "entity_id": "light.test_state",
                                },
                                "turn_off": {
                                    "service": "light.turn_off",
                                    "entity_id": "light.test_state",
                                },
                                "set_level": {
                                    "service": "light.turn_on",
                                    "data_template": {
                                        "entity_id": "light.test_state",
                                        "brightness": "{{brightness}}",
                                    },
                                },
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state is not None

        assert state.attributes.get("friendly_name") == "Template light"

    def test_icon_template(self):
        """Test icon template."""
        with assert_setup_component(1, "light"):
            assert setup.setup_component(
                self.hass,
                "light",
                {
                    "light": {
                        "platform": "template",
                        "lights": {
                            "test_template_light": {
                                "friendly_name": "Template light",
                                "value_template": "{{ 1 == 1 }}",
                                "turn_on": {
                                    "service": "light.turn_on",
                                    "entity_id": "light.test_state",
                                },
                                "turn_off": {
                                    "service": "light.turn_off",
                                    "entity_id": "light.test_state",
                                },
                                "set_level": {
                                    "service": "light.turn_on",
                                    "data_template": {
                                        "entity_id": "light.test_state",
                                        "brightness": "{{brightness}}",
                                    },
                                },
                                "icon_template": "{% if states.light.test_state.state %}"
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

        state = self.hass.states.get("light.test_template_light")
        assert state.attributes.get("icon") == ""

        state = self.hass.states.set("light.test_state", STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")

        assert state.attributes["icon"] == "mdi:check"

    def test_entity_picture_template(self):
        """Test entity_picture template."""
        with assert_setup_component(1, "light"):
            assert setup.setup_component(
                self.hass,
                "light",
                {
                    "light": {
                        "platform": "template",
                        "lights": {
                            "test_template_light": {
                                "friendly_name": "Template light",
                                "value_template": "{{ 1 == 1 }}",
                                "turn_on": {
                                    "service": "light.turn_on",
                                    "entity_id": "light.test_state",
                                },
                                "turn_off": {
                                    "service": "light.turn_off",
                                    "entity_id": "light.test_state",
                                },
                                "set_level": {
                                    "service": "light.turn_on",
                                    "data_template": {
                                        "entity_id": "light.test_state",
                                        "brightness": "{{brightness}}",
                                    },
                                },
                                "entity_picture_template": "{% if states.light.test_state.state %}"
                                "/local/light.png"
                                "{% endif %}",
                            }
                        },
                    }
                },
            )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state.attributes.get("entity_picture") == ""

        state = self.hass.states.set("light.test_state", STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")

        assert state.attributes["entity_picture"] == "/local/light.png"

    def test_color_action_no_template(self):
        """Test setting color with optimistic template."""
        assert setup.setup_component(
            self.hass,
            "light",
            {
                "light": {
                    "platform": "template",
                    "lights": {
                        "test_template_light": {
                            "value_template": "{{1 == 1}}",
                            "turn_on": {
                                "service": "light.turn_on",
                                "entity_id": "light.test_state",
                            },
                            "turn_off": {
                                "service": "light.turn_off",
                                "entity_id": "light.test_state",
                            },
                            "set_color": [
                                {
                                    "service": "test.automation",
                                    "data_template": {
                                        "entity_id": "test.test_state",
                                        "h": "{{h}}",
                                        "s": "{{s}}",
                                    },
                                },
                                {
                                    "service": "test.automation",
                                    "data_template": {
                                        "entity_id": "test.test_state",
                                        "s": "{{s}}",
                                        "h": "{{h}}",
                                    },
                                },
                            ],
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get("light.test_template_light")
        assert state.attributes.get("hs_color") is None

        common.turn_on(
            self.hass, "light.test_template_light", **{ATTR_HS_COLOR: (40, 50)}
        )
        self.hass.block_till_done()
        assert len(self.calls) == 2
        assert self.calls[0].data["h"] == "40"
        assert self.calls[0].data["s"] == "50"
        assert self.calls[1].data["h"] == "40"
        assert self.calls[1].data["s"] == "50"

        state = self.hass.states.get("light.test_template_light")
        _LOGGER.info(str(state.attributes))
        assert state is not None
        assert self.calls[0].data["h"] == "40"
        assert self.calls[0].data["s"] == "50"
        assert self.calls[1].data["h"] == "40"
        assert self.calls[1].data["s"] == "50"

    @pytest.mark.parametrize(
        "expected_hs,template",
        [
            ((360, 100), "{{(360, 100)}}"),
            ((359.9, 99.9), "{{(359.9, 99.9)}}"),
            (None, "{{(361, 100)}}"),
            (None, "{{(360, 101)}}"),
            (None, "{{x - 12}}"),
            (None, ""),
            (None, "{{ none }}"),
        ],
    )
    def test_color_template(self, expected_hs, template):
        """Test the template for the color."""
        with assert_setup_component(1, "light"):
            assert setup.setup_component(
                self.hass,
                "light",
                {
                    "light": {
                        "platform": "template",
                        "lights": {
                            "test_template_light": {
                                "value_template": "{{ 1 == 1 }}",
                                "turn_on": {
                                    "service": "light.turn_on",
                                    "entity_id": "light.test_state",
                                },
                                "turn_off": {
                                    "service": "light.turn_off",
                                    "entity_id": "light.test_state",
                                },
                                "set_color": [
                                    {
                                        "service": "input_number.set_value",
                                        "data_template": {
                                            "entity_id": "input_number.h",
                                            "color_temp": "{{h}}",
                                        },
                                    }
                                ],
                                "color_template": template,
                            }
                        },
                    }
                },
            )
        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()
        state = self.hass.states.get("light.test_template_light")
        assert state is not None
        assert state.attributes.get("hs_color") == expected_hs


async def test_available_template_with_entities(hass):
    """Test availability templates with values from other entities."""
    await setup.async_setup_component(
        hass,
        "light",
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "availability_template": "{{ is_state('availability_boolean.state', 'on') }}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # When template returns true..
    hass.states.async_set(_STATE_AVAILABILITY_BOOLEAN, STATE_ON)
    await hass.async_block_till_done()

    # Device State should not be unavailable
    assert hass.states.get("light.test_template_light").state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set(_STATE_AVAILABILITY_BOOLEAN, STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert hass.states.get("light.test_template_light").state == STATE_UNAVAILABLE


async def test_invalid_availability_template_keeps_component_available(hass, caplog):
    """Test that an invalid availability keeps the device available."""
    await setup.async_setup_component(
        hass,
        "light",
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "availability_template": "{{ x - 12 }}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("light.test_template_light").state != STATE_UNAVAILABLE
    assert ("UndefinedError: 'x' is undefined") in caplog.text
