"""The tests for the  Template switch platform."""

import pytest

from homeassistant import setup
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import CoreState, State
from homeassistant.setup import async_setup_component

from tests.common import (
    assert_setup_component,
    async_mock_service,
    mock_component,
    mock_restore_cache,
)
from tests.components.switch import common


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_template_state_text(hass):
    """Test the state text of a template."""
    with assert_setup_component(1, "switch"):
        assert await async_setup_component(
            hass,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_ON

    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_OFF


async def test_template_state_boolean_on(hass):
    """Test the setting of the state with boolean on."""
    with assert_setup_component(1, "switch"):
        assert await async_setup_component(
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
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_ON


async def test_template_state_boolean_off(hass):
    """Test the setting of the state with off."""
    with assert_setup_component(1, "switch"):
        assert await async_setup_component(
            hass,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_OFF


async def test_icon_template(hass):
    """Test icon template."""
    with assert_setup_component(1, "switch"):
        assert await async_setup_component(
            hass,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.attributes.get("icon") == ""

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.attributes["icon"] == "mdi:check"


async def test_entity_picture_template(hass):
    """Test entity_picture template."""
    with assert_setup_component(1, "switch"):
        assert await async_setup_component(
            hass,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.attributes.get("entity_picture") == ""

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.attributes["entity_picture"] == "/local/switch.png"


async def test_template_syntax_error(hass):
    """Test templating syntax error."""
    with assert_setup_component(0, "switch"):
        assert await async_setup_component(
            hass,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_invalid_name_does_not_create(hass):
    """Test invalid name."""
    with assert_setup_component(0, "switch"):
        assert await async_setup_component(
            hass,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_invalid_switch_does_not_create(hass):
    """Test invalid switch."""
    with assert_setup_component(0, "switch"):
        assert await async_setup_component(
            hass,
            "switch",
            {
                "switch": {
                    "platform": "template",
                    "switches": {"test_template_switch": "Invalid"},
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_no_switches_does_not_create(hass):
    """Test if there are no switches no creation."""
    with assert_setup_component(0, "switch"):
        assert await async_setup_component(
            hass, "switch", {"switch": {"platform": "template"}}
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_missing_on_does_not_create(hass):
    """Test missing on."""
    with assert_setup_component(0, "switch"):
        assert await async_setup_component(
            hass,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_missing_off_does_not_create(hass):
    """Test missing off."""
    with assert_setup_component(0, "switch"):
        assert await async_setup_component(
            hass,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_on_action(hass, calls):
    """Test on action."""
    assert await async_setup_component(
        hass,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, "switch.test_template_switch")
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_on_action_optimistic(hass, calls):
    """Test on action in optimistic mode."""
    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    "test_template_switch": {
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

    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_template_switch", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, "switch.test_template_switch")
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert len(calls) == 1
    assert state.state == STATE_ON


async def test_off_action(hass, calls):
    """Test off action."""
    assert await async_setup_component(
        hass,
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

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_ON

    await common.async_turn_off(hass, "switch.test_template_switch")
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_off_action_optimistic(hass, calls):
    """Test off action in optimistic mode."""
    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    "test_template_switch": {
                        "turn_off": {"service": "test.automation"},
                        "turn_on": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                    }
                },
            }
        },
    )

    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_template_switch", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_ON

    await common.async_turn_off(hass, "switch.test_template_switch")
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert len(calls) == 1
    assert state.state == STATE_OFF


async def test_restore_state(hass):
    """Test state restoration."""
    mock_restore_cache(
        hass,
        (
            State("switch.s1", STATE_ON),
            State("switch.s2", STATE_OFF),
        ),
    )

    hass.state = CoreState.starting
    mock_component(hass, "recorder")

    await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    "s1": {
                        "turn_on": {"service": "test.automation"},
                        "turn_off": {"service": "test.automation"},
                    },
                    "s2": {
                        "turn_on": {"service": "test.automation"},
                        "turn_off": {"service": "test.automation"},
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.s1")
    assert state
    assert state.state == STATE_ON

    state = hass.states.get("switch.s2")
    assert state
    assert state.state == STATE_OFF


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


async def test_unique_id(hass):
    """Test unique_id option only creates one switch per id."""
    await setup.async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    "test_template_switch_01": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ true }}",
                        "turn_on": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "turn_off": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                    },
                    "test_template_switch_02": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ false }}",
                        "turn_on": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "turn_off": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                    },
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
