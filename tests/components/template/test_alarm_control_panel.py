"""The tests for the Template alarm control panel platform."""
import pytest

from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)

from tests.components.alarm_control_panel import common

TEMPLATE_NAME = "alarm_control_panel.test_template_panel"
PANEL_NAME = "alarm_control_panel.test"


@pytest.mark.parametrize("count,domain", [(1, "alarm_control_panel")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "alarm_control_panel": {
                "platform": "template",
                "panels": {
                    "test_template_panel": {
                        "value_template": "{{ states('alarm_control_panel.test') }}",
                        "arm_away": {
                            "service": "alarm_control_panel.alarm_arm_away",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                        "arm_home": {
                            "service": "alarm_control_panel.alarm_arm_home",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                        "arm_night": {
                            "service": "alarm_control_panel.alarm_arm_night",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                        "disarm": {
                            "service": "alarm_control_panel.alarm_disarm",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                    }
                },
            }
        },
    ],
)
async def test_template_state_text(hass, start_ha):
    """Test the state text of a template."""

    for set_state in [
        STATE_ALARM_ARMED_HOME,
        STATE_ALARM_ARMED_AWAY,
        STATE_ALARM_ARMED_NIGHT,
        STATE_ALARM_ARMING,
        STATE_ALARM_DISARMED,
        STATE_ALARM_PENDING,
        STATE_ALARM_TRIGGERED,
    ]:
        hass.states.async_set(PANEL_NAME, set_state)
        await hass.async_block_till_done()
        state = hass.states.get(TEMPLATE_NAME)
        assert state.state == set_state

    hass.states.async_set(PANEL_NAME, "invalid_state")
    await hass.async_block_till_done()
    state = hass.states.get(TEMPLATE_NAME)
    assert state.state == "unknown"


@pytest.mark.parametrize("count,domain", [(1, "alarm_control_panel")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "alarm_control_panel": {
                "platform": "template",
                "panels": {
                    "test_template_panel": {
                        "arm_away": {
                            "service": "alarm_control_panel.alarm_arm_away",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                        "arm_home": {
                            "service": "alarm_control_panel.alarm_arm_home",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                        "arm_night": {
                            "service": "alarm_control_panel.alarm_arm_night",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                        "disarm": {
                            "service": "alarm_control_panel.alarm_disarm",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                    }
                },
            }
        },
    ],
)
async def test_optimistic_states(hass, start_ha):
    """Test the optimistic state."""

    state = hass.states.get(TEMPLATE_NAME)
    await hass.async_block_till_done()
    assert state.state == "unknown"

    for func, set_state in [
        (common.async_alarm_arm_away, STATE_ALARM_ARMED_AWAY),
        (common.async_alarm_arm_home, STATE_ALARM_ARMED_HOME),
        (common.async_alarm_arm_night, STATE_ALARM_ARMED_NIGHT),
        (common.async_alarm_disarm, STATE_ALARM_DISARMED),
    ]:
        await func(hass, entity_id=TEMPLATE_NAME)
        await hass.async_block_till_done()
        assert hass.states.get(TEMPLATE_NAME).state == set_state


@pytest.mark.parametrize("count,domain", [(0, "alarm_control_panel")])
@pytest.mark.parametrize(
    "config,msg",
    [
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "{% if blah %}",
                            "arm_away": {
                                "service": "alarm_control_panel.alarm_arm_away",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_home": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_night": {
                                "service": "alarm_control_panel.alarm_arm_night",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "disarm": {
                                "service": "alarm_control_panel.alarm_disarm",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                        }
                    },
                }
            },
            "invalid template",
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "bad name here": {
                            "value_template": "disarmed",
                            "arm_away": {
                                "service": "alarm_control_panel.alarm_arm_away",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_home": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_night": {
                                "service": "alarm_control_panel.alarm_arm_night",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "disarm": {
                                "service": "alarm_control_panel.alarm_disarm",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                        }
                    },
                }
            },
            "invalid slug bad name",
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "wibble": {"test_panel": "Invalid"},
                }
            },
            "[wibble] is an invalid option",
        ),
        (
            {
                "alarm_control_panel": {"platform": "template"},
            },
            "required key not provided @ data['panels']",
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "disarmed",
                            "arm_away": {
                                "service": "alarm_control_panel.alarm_arm_away",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_home": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_night": {
                                "service": "alarm_control_panel.alarm_arm_night",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "disarm": {
                                "service": "alarm_control_panel.alarm_disarm",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "code_format": "bad_format",
                        }
                    },
                }
            },
            "value must be one of ['no_code', 'number', 'text']",
        ),
    ],
)
async def test_template_syntax_error(hass, msg, start_ha, caplog_setup_text):
    """Test templating syntax error."""
    assert len(hass.states.async_all("alarm_control_panel")) == 0
    assert (msg) in caplog_setup_text


@pytest.mark.parametrize("count,domain", [(1, "alarm_control_panel")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "alarm_control_panel": {
                "platform": "template",
                "panels": {
                    "test_template_panel": {
                        "name": "Template Alarm Panel",
                        "value_template": "disarmed",
                        "arm_away": {
                            "service": "alarm_control_panel.alarm_arm_away",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                        "arm_home": {
                            "service": "alarm_control_panel.alarm_arm_home",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                        "arm_night": {
                            "service": "alarm_control_panel.alarm_arm_night",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                        "disarm": {
                            "service": "alarm_control_panel.alarm_disarm",
                            "entity_id": "alarm_control_panel.test",
                            "data": {"code": "1234"},
                        },
                    }
                },
            }
        },
    ],
)
async def test_name(hass, start_ha):
    """Test the accessibility of the name attribute."""
    state = hass.states.get(TEMPLATE_NAME)
    assert state is not None
    assert state.attributes.get("friendly_name") == "Template Alarm Panel"


@pytest.mark.parametrize("count,domain", [(1, "alarm_control_panel")])
@pytest.mark.parametrize(
    "config,func",
    [
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "{{ states('alarm_control_panel.test') }}",
                            "arm_away": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_home": {"service": "test.automation"},
                            "arm_night": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "disarm": {
                                "service": "alarm_control_panel.alarm_disarm",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                        }
                    },
                }
            },
            common.async_alarm_arm_home,
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "{{ states('alarm_control_panel.test') }}",
                            "arm_home": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_away": {"service": "test.automation"},
                            "arm_night": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "disarm": {
                                "service": "alarm_control_panel.alarm_disarm",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                        }
                    },
                },
            },
            common.async_alarm_arm_away,
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "{{ states('alarm_control_panel.test') }}",
                            "arm_home": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_night": {"service": "test.automation"},
                            "arm_away": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "disarm": {
                                "service": "alarm_control_panel.alarm_disarm",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                        }
                    },
                }
            },
            common.async_alarm_arm_night,
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "{{ states('alarm_control_panel.test') }}",
                            "arm_home": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "disarm": {"service": "test.automation"},
                            "arm_away": {
                                "service": "alarm_control_panel.alarm_arm_home",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                            "arm_night": {
                                "service": "alarm_control_panel.alarm_disarm",
                                "entity_id": "alarm_control_panel.test",
                                "data": {"code": "1234"},
                            },
                        }
                    },
                }
            },
            common.async_alarm_disarm,
        ),
    ],
)
async def test_arm_home_action(hass, func, start_ha, calls):
    """Test arm home action."""
    await func(hass, entity_id=TEMPLATE_NAME)
    await hass.async_block_till_done()
    assert len(calls) == 1


@pytest.mark.parametrize("count,domain", [(1, "alarm_control_panel")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "alarm_control_panel": {
                "platform": "template",
                "panels": {
                    "test_template_alarm_control_panel_01": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ true }}",
                    },
                    "test_template_alarm_control_panel_02": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ false }}",
                    },
                },
            },
        },
    ],
)
async def test_unique_id(hass, start_ha):
    """Test unique_id option only creates one alarm control panel per id."""
    assert len(hass.states.async_all()) == 1


@pytest.mark.parametrize("count,domain", [(1, "alarm_control_panel")])
@pytest.mark.parametrize(
    "config,code_format,code_arm_required",
    [
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "disarmed",
                        }
                    },
                }
            },
            "number",
            True,
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "disarmed",
                            "code_format": "text",
                        }
                    },
                }
            },
            "text",
            True,
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "disarmed",
                            "code_format": "no_code",
                            "code_arm_required": False,
                        }
                    },
                }
            },
            None,
            False,
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "test_template_panel": {
                            "value_template": "disarmed",
                            "code_format": "text",
                            "code_arm_required": False,
                        }
                    },
                }
            },
            "text",
            False,
        ),
    ],
)
async def test_code_config(hass, code_format, code_arm_required, start_ha):
    """Test configuration options related to alarm code."""
    state = hass.states.get(TEMPLATE_NAME)
    assert state.attributes.get("code_format") == code_format
    assert state.attributes.get("code_arm_required") == code_arm_required
