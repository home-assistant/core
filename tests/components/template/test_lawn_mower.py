"""The tests for the Template lawn_mower platform."""

import pytest

from homeassistant import setup
from homeassistant.components.lawn_mower import (
    DOMAIN,
    SERVICE_DOCK,
    SERVICE_PAUSE,
    SERVICE_START_MOWING,
    LawnMowerActivity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import assert_setup_component

_TEST_LAWN_MOWER = "lawn_mower.test_lawn_mower"
_STATE_INPUT_SELECT = "input_select.state"


@pytest.mark.parametrize(("count", "domain"), [(1, "lawn_mower")])
@pytest.mark.parametrize(
    ("parm1", "config"),
    [
        (
            STATE_UNKNOWN,
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {
                        "test_lawn_mower": {
                            "start_mowing": {"service": "script.lawn_mower_start"}
                        }
                    },
                }
            },
        ),
        (
            LawnMowerActivity.MOWING,
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {
                        "test_lawn_mower": {"value_template": "{{ 'mowing' }}"}
                    },
                }
            },
        ),
        (
            LawnMowerActivity.MOWING,
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {
                        "test_lawn_mower": {
                            "value_template": "{{ 'mowing' }}",
                            "start_mowing": {"service": "script.lawn_mower_start"},
                        },
                    },
                }
            },
        ),
        (
            STATE_UNKNOWN,
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {
                        "test_lawn_mower": {"value_template": "{{ 'abc' }}"}
                    },
                }
            },
        ),
        (
            STATE_UNKNOWN,
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {
                        "test_lawn_mower": {
                            "value_template": "{{ this_function_does_not_exist() }}",
                            "start_mowing": {"service": "script.lawn_mower_start"},
                        }
                    },
                }
            },
        ),
        (
            STATE_UNKNOWN,
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {"test_lawn_mower": {}},
                }
            },
        ),
    ],
)
async def test_valid_configs(hass: HomeAssistant, count, parm1, start_ha) -> None:
    """Test: configs."""
    assert len(hass.states.async_all("lawn_mower")) == count
    _verify(hass, parm1)


@pytest.mark.parametrize(
    ("count", "domain", "config"),
    [
        (
            1,
            "lawn_mower",
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {
                        "test_lawn_mower": {
                            "value_template": "{{ states('input_select.state') }}",
                            "start_mowing": {"service": "script.lawn_mower_start"},
                        }
                    },
                }
            },
        )
    ],
)
async def test_templates_with_entities(hass: HomeAssistant, start_ha) -> None:
    """Test templates with values from other entities."""
    _verify(hass, STATE_UNKNOWN)

    hass.states.async_set(_STATE_INPUT_SELECT, LawnMowerActivity.MOWING)
    await hass.async_block_till_done()
    _verify(hass, LawnMowerActivity.MOWING)


@pytest.mark.parametrize(
    ("count", "domain", "config"),
    [
        (
            1,
            "lawn_mower",
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {
                        "test_template_lawn_mower": {
                            "availability_template": "{{ is_state('availability_state.state', 'on') }}",
                            "start_mowing": {"service": "script.lawn_mower_start"},
                        }
                    },
                }
            },
        )
    ],
)
async def test_available_template_with_entities(hass: HomeAssistant, start_ha) -> None:
    """Test availability templates with values from other entities."""

    # When template returns true..
    hass.states.async_set("availability_state.state", STATE_ON)
    await hass.async_block_till_done()

    # Device State should not be unavailable
    assert (
        hass.states.get("lawn_mower.test_template_lawn_mower").state
        != STATE_UNAVAILABLE
    )

    # When Availability template returns false
    hass.states.async_set("availability_state.state", STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert (
        hass.states.get("lawn_mower.test_template_lawn_mower").state
        == STATE_UNAVAILABLE
    )


@pytest.mark.parametrize(
    ("count", "domain", "config"),
    [
        (
            1,
            "lawn_mower",
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {
                        "test_template_lawn_mower": {
                            "availability_template": "{{ x - 12 }}",
                            "start_mowing": {"service": "script.lawn_mower_start"},
                        }
                    },
                }
            },
        )
    ],
)
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, start_ha, caplog_setup_text
) -> None:
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get("lawn_mower.test_template_lawn_mower") != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog_setup_text


@pytest.mark.parametrize(
    ("count", "domain", "config"),
    [
        (
            1,
            "lawn_mower",
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {
                        "test_template_lawn_mower": {
                            "value_template": "{{ 'cleaning' }}",
                            "start_mowing": {"service": "script.lawn_mower_start"},
                            "attribute_templates": {
                                "test_attribute": "It {{ states.sensor.test_state.state }}."
                            },
                        }
                    },
                }
            },
        )
    ],
)
async def test_attribute_templates(hass: HomeAssistant, start_ha) -> None:
    """Test attribute_templates template."""
    state = hass.states.get("lawn_mower.test_template_lawn_mower")
    assert state.attributes["test_attribute"] == "It ."

    hass.states.async_set("sensor.test_state", "Works")
    await hass.async_block_till_done()
    await async_update_entity(hass, "lawn_mower.test_template_lawn_mower")
    state = hass.states.get("lawn_mower.test_template_lawn_mower")
    assert state.attributes["test_attribute"] == "It Works."


@pytest.mark.parametrize(
    ("count", "domain", "config"),
    [
        (
            1,
            "lawn_mower",
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {
                        "invalid_template": {
                            "value_template": "{{ states('input_select.state') }}",
                            "start_mowing": {"service": "script.lawn_mower_start"},
                            "attribute_templates": {
                                "test_attribute": "{{ this_function_does_not_exist() }}"
                            },
                        }
                    },
                }
            },
        )
    ],
)
async def test_invalid_attribute_template(
    hass: HomeAssistant, start_ha, caplog_setup_text
) -> None:
    """Test that errors are logged if rendering template fails."""
    assert len(hass.states.async_all("lawn_mower")) == 1
    assert "test_attribute" in caplog_setup_text
    assert "TemplateError" in caplog_setup_text


@pytest.mark.parametrize(
    ("count", "domain", "config"),
    [
        (
            1,
            "lawn_mower",
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {
                        "test_template_lawn_mower_01": {
                            "unique_id": "not-so-unique-anymore",
                            "value_template": "{{ true }}",
                            "start_mowing": {"service": "script.lawn_mower_start"},
                        },
                        "test_template_lawn_mower_02": {
                            "unique_id": "not-so-unique-anymore",
                            "value_template": "{{ false }}",
                            "start_mowing": {"service": "script.lawn_mower_start"},
                        },
                    },
                }
            },
        ),
    ],
)
async def test_unique_id(hass: HomeAssistant, start_ha) -> None:
    """Test unique_id option only creates one lawn_mower per id."""
    assert len(hass.states.async_all("lawn_mower")) == 1


async def test_unused_services(hass: HomeAssistant) -> None:
    """Test calling unused services raises."""
    await _register_basic_lawn_mower(hass)

    data = {ATTR_ENTITY_ID: _TEST_LAWN_MOWER}

    # Start mowing lawn_mower
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, SERVICE_START_MOWING, data, blocking=True
        )
    await hass.async_block_till_done()

    # Pause lawn_mower
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, SERVICE_PAUSE, data, blocking=True)
    await hass.async_block_till_done()

    # Dock lawn_mower
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, SERVICE_DOCK, data, blocking=True)
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN)


async def test_state_services(hass: HomeAssistant, calls) -> None:
    """Test state services."""
    await _register_components(hass)

    data = {ATTR_ENTITY_ID: _TEST_LAWN_MOWER}

    # Start lawn_mower
    await hass.services.async_call(DOMAIN, SERVICE_START_MOWING, data, blocking=True)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_SELECT).state == LawnMowerActivity.MOWING
    _verify(hass, LawnMowerActivity.MOWING)
    assert len(calls) == 1
    assert calls[-1].data["action"] == "start_mowing"
    assert calls[-1].data["caller"] == _TEST_LAWN_MOWER

    # Pause lawn_mower
    await hass.services.async_call(DOMAIN, SERVICE_PAUSE, data, blocking=True)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_SELECT).state == LawnMowerActivity.PAUSED
    _verify(hass, LawnMowerActivity.PAUSED)
    assert len(calls) == 2
    assert calls[-1].data["action"] == "pause"
    assert calls[-1].data["caller"] == _TEST_LAWN_MOWER

    # Return lawn_mower to base
    await hass.services.async_call(DOMAIN, SERVICE_DOCK, data, blocking=True)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_SELECT).state == LawnMowerActivity.DOCKED
    _verify(hass, LawnMowerActivity.DOCKED)
    assert len(calls) == 3
    assert calls[-1].data["action"] == "dock"
    assert calls[-1].data["caller"] == _TEST_LAWN_MOWER


def _verify(hass: HomeAssistant, expected_state: str):
    """Verify lawn mower's state."""
    state = hass.states.get(_TEST_LAWN_MOWER)
    assert state.state == expected_state


async def _register_basic_lawn_mower(hass: HomeAssistant):
    """Register basic lawn mower with only required options for testing."""
    with assert_setup_component(1, "input_select"):
        assert await setup.async_setup_component(
            hass,
            "input_select",
            {
                "input_select": {
                    "state": {"name": "State", "options": [LawnMowerActivity.MOWING]}
                }
            },
        )

    with assert_setup_component(1, "lawn_mower"):
        assert await setup.async_setup_component(
            hass,
            "lawn_mower",
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {"test_lawn_mower": {}},
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def _register_components(hass: HomeAssistant):
    """Register basic components for testing."""
    with assert_setup_component(1, "input_select"):
        assert await setup.async_setup_component(
            hass,
            "input_select",
            {
                "input_select": {
                    "state": {
                        "name": "State",
                        "options": [
                            LawnMowerActivity.DOCKED,
                            LawnMowerActivity.ERROR,
                            LawnMowerActivity.MOWING,
                            LawnMowerActivity.PAUSED,
                        ],
                    },
                }
            },
        )

    with assert_setup_component(1, "lawn_mower"):
        test_lawn_mower_config = {
            "value_template": "{{ states('input_select.state') }}",
            "start_mowing": [
                {
                    "service": "input_select.select_option",
                    "data": {
                        "entity_id": _STATE_INPUT_SELECT,
                        "option": LawnMowerActivity.MOWING,
                    },
                },
                {
                    "service": "test.automation",
                    "data_template": {
                        "action": "start_mowing",
                        "caller": "{{ this.entity_id }}",
                    },
                },
            ],
            "pause": [
                {
                    "service": "input_select.select_option",
                    "data": {
                        "entity_id": _STATE_INPUT_SELECT,
                        "option": LawnMowerActivity.PAUSED,
                    },
                },
                {
                    "service": "test.automation",
                    "data_template": {
                        "action": "pause",
                        "caller": "{{ this.entity_id }}",
                    },
                },
            ],
            "dock": [
                {
                    "service": "input_select.select_option",
                    "data": {
                        "entity_id": _STATE_INPUT_SELECT,
                        "option": LawnMowerActivity.DOCKED,
                    },
                },
                {
                    "service": "test.automation",
                    "data_template": {
                        "action": "dock",
                        "caller": "{{ this.entity_id }}",
                    },
                },
            ],
            "attribute_templates": {
                "test_attribute": "It {{ states.sensor.test_state.state }}."
            },
        }

        assert await setup.async_setup_component(
            hass,
            "lawn_mower",
            {
                "lawn_mower": {
                    "platform": "template",
                    "lawn_mowers": {"test_lawn_mower": test_lawn_mower_config},
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()
