"""The tests for the  Template light platform."""
import logging

import pytest

from homeassistant import setup
import homeassistant.components.light as light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)

from tests.common import assert_setup_component, async_mock_service

_LOGGER = logging.getLogger(__name__)

# Represent for light's availability
_STATE_AVAILABILITY_BOOLEAN = "availability_boolean.state"


@pytest.fixture(name="calls")
def fixture_calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_template_state_invalid(hass):
    """Test template state with render error."""
    with assert_setup_component(1, light.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF


async def test_template_state_text(hass):
    """Test the state text of a template."""
    with assert_setup_component(1, light.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON

    state = hass.states.async_set("light.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "expected_state,template",
    [(STATE_ON, "{{ 1 == 1 }}"), (STATE_OFF, "{{ 1 == 2 }}")],
)
async def test_template_state_boolean(hass, expected_state, template):
    """Test the setting of the state with boolean on."""
    with assert_setup_component(1, light.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == expected_state


async def test_template_syntax_error(hass):
    """Test templating syntax error."""
    with assert_setup_component(0, light.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_invalid_name_does_not_create(hass):
    """Test invalid name."""
    with assert_setup_component(0, light.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_invalid_light_does_not_create(hass):
    """Test invalid light."""
    with assert_setup_component(0, light.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            light.DOMAIN,
            {
                "light": {
                    "platform": "template",
                    "switches": {"test_template_light": "Invalid"},
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_no_lights_does_not_create(hass):
    """Test if there are no lights no creation."""
    with assert_setup_component(0, light.DOMAIN):
        assert await setup.async_setup_component(
            hass, "light", {"light": {"platform": "template"}}
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


@pytest.mark.parametrize(
    "missing_key, count", [("value_template", 1), ("turn_on", 0), ("turn_off", 0)]
)
async def test_missing_key(hass, missing_key, count):
    """Test missing template."""
    light_config = {
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

    del light_config["light"]["lights"]["light_one"][missing_key]
    with assert_setup_component(count, light.DOMAIN):
        assert await setup.async_setup_component(hass, "light", light_config)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    if count:
        assert hass.states.async_all() != []
    else:
        assert hass.states.async_all() == []


async def test_on_action(hass, calls):
    """Test on action."""
    assert await setup.async_setup_component(
        hass,
        light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("light.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light"},
        blocking=True,
    )

    assert len(calls) == 1


async def test_on_action_optimistic(hass, calls):
    """Test on action with optimistic state."""
    assert await setup.async_setup_component(
        hass,
        light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("light.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light"},
        blocking=True,
    )

    state = hass.states.get("light.test_template_light")
    assert len(calls) == 1
    assert state.state == STATE_ON


async def test_off_action(hass, calls):
    """Test off action."""
    assert await setup.async_setup_component(
        hass,
        light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_template_light"},
        blocking=True,
    )

    assert len(calls) == 1


async def test_off_action_optimistic(hass, calls):
    """Test off action with optimistic state."""
    assert await setup.async_setup_component(
        hass,
        light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_template_light"},
        blocking=True,
    )

    assert len(calls) == 1
    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF


async def test_white_value_action_no_template(hass, calls):
    """Test setting white value with optimistic template."""
    assert await setup.async_setup_component(
        hass,
        light.DOMAIN,
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
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("white_value") is None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_WHITE_VALUE: 124},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["white_value"] == 124

    state = hass.states.get("light.test_template_light")
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
async def test_white_value_template(hass, expected_white_value, template):
    """Test the template for the white value."""
    with assert_setup_component(1, light.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("white_value") == expected_white_value


async def test_level_action_no_template(hass, calls):
    """Test setting brightness with optimistic template."""
    assert await setup.async_setup_component(
        hass,
        light.DOMAIN,
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
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("brightness") is None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_BRIGHTNESS: 124},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["brightness"] == 124

    state = hass.states.get("light.test_template_light")
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
async def test_level_template(hass, expected_level, template):
    """Test the template for the level."""
    with assert_setup_component(1, light.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
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
async def test_temperature_template(hass, expected_temp, template):
    """Test the template for the temperature."""
    with assert_setup_component(1, light.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("color_temp") == expected_temp


async def test_temperature_action_no_template(hass, calls):
    """Test setting temperature with optimistic template."""
    assert await setup.async_setup_component(
        hass,
        light.DOMAIN,
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
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("color_template") is None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_COLOR_TEMP: 345},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["color_temp"] == 345

    state = hass.states.get("light.test_template_light")
    _LOGGER.info(str(state.attributes))
    assert state is not None
    assert state.attributes.get("color_temp") == 345


async def test_friendly_name(hass):
    """Test the accessibility of the friendly_name attribute."""
    with assert_setup_component(1, light.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state is not None

    assert state.attributes.get("friendly_name") == "Template light"


async def test_icon_template(hass):
    """Test icon template."""
    with assert_setup_component(1, light.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("icon") == ""

    state = hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")

    assert state.attributes["icon"] == "mdi:check"


async def test_entity_picture_template(hass):
    """Test entity_picture template."""
    with assert_setup_component(1, light.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            light.DOMAIN,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("entity_picture") == ""

    state = hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")

    assert state.attributes["entity_picture"] == "/local/light.png"


async def test_color_action_no_template(hass, calls):
    """Test setting color with optimistic template."""
    assert await setup.async_setup_component(
        hass,
        light.DOMAIN,
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
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("hs_color") is None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_HS_COLOR: (40, 50)},
        blocking=True,
    )

    assert len(calls) == 2
    assert calls[0].data["h"] == 40
    assert calls[0].data["s"] == 50
    assert calls[1].data["h"] == 40
    assert calls[1].data["s"] == 50

    state = hass.states.get("light.test_template_light")
    _LOGGER.info(str(state.attributes))
    assert state is not None
    assert calls[0].data["h"] == 40
    assert calls[0].data["s"] == 50
    assert calls[1].data["h"] == 40
    assert calls[1].data["s"] == 50


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
async def test_color_template(hass, expected_hs, template):
    """Test the template for the color."""
    with assert_setup_component(1, light.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            light.DOMAIN,
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
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("hs_color") == expected_hs


async def test_available_template_with_entities(hass):
    """Test availability templates with values from other entities."""
    await setup.async_setup_component(
        hass,
        light.DOMAIN,
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
        light.DOMAIN,
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


async def test_unique_id(hass):
    """Test unique_id option only creates one light per id."""
    await setup.async_setup_component(
        hass,
        light.DOMAIN,
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light_01": {
                        "unique_id": "not-so-unique-anymore",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                    },
                    "test_template_light_02": {
                        "unique_id": "not-so-unique-anymore",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                    },
                },
            },
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
