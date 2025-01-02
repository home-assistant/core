"""The tests for the Template vacuum platform."""

import pytest

from homeassistant import setup
from homeassistant.components.vacuum import ATTR_BATTERY_LEVEL, VacuumActivity
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import assert_setup_component
from tests.components.vacuum import common

_TEST_VACUUM = "vacuum.test_vacuum"
_STATE_INPUT_SELECT = "input_select.state"
_SPOT_CLEANING_INPUT_BOOLEAN = "input_boolean.spot_cleaning"
_LOCATING_INPUT_BOOLEAN = "input_boolean.locating"
_FAN_SPEED_INPUT_SELECT = "input_select.fan_speed"
_BATTERY_LEVEL_INPUT_NUMBER = "input_number.battery_level"


@pytest.mark.parametrize(("count", "domain"), [(1, "vacuum")])
@pytest.mark.parametrize(
    ("parm1", "parm2", "config"),
    [
        (
            STATE_UNKNOWN,
            None,
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_vacuum": {"start": {"service": "script.vacuum_start"}}
                    },
                }
            },
        ),
        (
            VacuumActivity.CLEANING,
            100,
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_vacuum": {
                            "value_template": "{{ 'cleaning' }}",
                            "battery_level_template": "{{ 100 }}",
                            "start": {"service": "script.vacuum_start"},
                        }
                    },
                }
            },
        ),
        (
            STATE_UNKNOWN,
            None,
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_vacuum": {
                            "value_template": "{{ 'abc' }}",
                            "battery_level_template": "{{ 101 }}",
                            "start": {"service": "script.vacuum_start"},
                        }
                    },
                }
            },
        ),
        (
            STATE_UNKNOWN,
            None,
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_vacuum": {
                            "value_template": "{{ this_function_does_not_exist() }}",
                            "battery_level_template": "{{ this_function_does_not_exist() }}",
                            "fan_speed_template": "{{ this_function_does_not_exist() }}",
                            "start": {"service": "script.vacuum_start"},
                        }
                    },
                }
            },
        ),
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_valid_configs(hass: HomeAssistant, count, parm1, parm2) -> None:
    """Test: configs."""
    assert len(hass.states.async_all("vacuum")) == count
    _verify(hass, parm1, parm2)


@pytest.mark.parametrize(("count", "domain"), [(0, "vacuum")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "vacuum": {
                "platform": "template",
                "vacuums": {"test_vacuum": {"value_template": "{{ 'on' }}"}},
            }
        },
        {
            "platform": "template",
            "vacuums": {"test_vacuum": {"start": {"service": "script.vacuum_start"}}},
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_invalid_configs(hass: HomeAssistant, count) -> None:
    """Test: configs."""
    assert len(hass.states.async_all("vacuum")) == count


@pytest.mark.parametrize(
    ("count", "domain", "config"),
    [
        (
            1,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_vacuum": {
                            "value_template": "{{ states('input_select.state') }}",
                            "battery_level_template": "{{ states('input_number.battery_level') }}",
                            "start": {"service": "script.vacuum_start"},
                        }
                    },
                }
            },
        )
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_templates_with_entities(hass: HomeAssistant) -> None:
    """Test templates with values from other entities."""
    _verify(hass, STATE_UNKNOWN, None)

    hass.states.async_set(_STATE_INPUT_SELECT, VacuumActivity.CLEANING)
    hass.states.async_set(_BATTERY_LEVEL_INPUT_NUMBER, 100)
    await hass.async_block_till_done()
    _verify(hass, VacuumActivity.CLEANING, 100)


@pytest.mark.parametrize(
    ("count", "domain", "config"),
    [
        (
            1,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_template_vacuum": {
                            "availability_template": "{{ is_state('availability_state.state', 'on') }}",
                            "start": {"service": "script.vacuum_start"},
                        }
                    },
                }
            },
        )
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability templates with values from other entities."""

    # When template returns true..
    hass.states.async_set("availability_state.state", STATE_ON)
    await hass.async_block_till_done()

    # Device State should not be unavailable
    assert hass.states.get("vacuum.test_template_vacuum").state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set("availability_state.state", STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert hass.states.get("vacuum.test_template_vacuum").state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("count", "domain", "config"),
    [
        (
            1,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_template_vacuum": {
                            "availability_template": "{{ x - 12 }}",
                            "start": {"service": "script.vacuum_start"},
                        }
                    },
                }
            },
        )
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog_setup_text
) -> None:
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get("vacuum.test_template_vacuum") != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog_setup_text


@pytest.mark.parametrize(
    ("count", "domain", "config"),
    [
        (
            1,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_template_vacuum": {
                            "value_template": "{{ 'cleaning' }}",
                            "start": {"service": "script.vacuum_start"},
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
@pytest.mark.usefixtures("start_ha")
async def test_attribute_templates(hass: HomeAssistant) -> None:
    """Test attribute_templates template."""
    state = hass.states.get("vacuum.test_template_vacuum")
    assert state.attributes["test_attribute"] == "It ."

    hass.states.async_set("sensor.test_state", "Works")
    await hass.async_block_till_done()
    await async_update_entity(hass, "vacuum.test_template_vacuum")
    state = hass.states.get("vacuum.test_template_vacuum")
    assert state.attributes["test_attribute"] == "It Works."


@pytest.mark.parametrize(
    ("count", "domain", "config"),
    [
        (
            1,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "invalid_template": {
                            "value_template": "{{ states('input_select.state') }}",
                            "start": {"service": "script.vacuum_start"},
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
@pytest.mark.usefixtures("start_ha")
async def test_invalid_attribute_template(
    hass: HomeAssistant, caplog_setup_text
) -> None:
    """Test that errors are logged if rendering template fails."""
    assert len(hass.states.async_all("vacuum")) == 1
    assert "test_attribute" in caplog_setup_text
    assert "TemplateError" in caplog_setup_text


@pytest.mark.parametrize(
    ("count", "domain", "config"),
    [
        (
            1,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_template_vacuum_01": {
                            "unique_id": "not-so-unique-anymore",
                            "value_template": "{{ true }}",
                            "start": {"service": "script.vacuum_start"},
                        },
                        "test_template_vacuum_02": {
                            "unique_id": "not-so-unique-anymore",
                            "value_template": "{{ false }}",
                            "start": {"service": "script.vacuum_start"},
                        },
                    },
                }
            },
        ),
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id option only creates one vacuum per id."""
    assert len(hass.states.async_all("vacuum")) == 1


async def test_unused_services(hass: HomeAssistant) -> None:
    """Test calling unused services raises."""
    await _register_basic_vacuum(hass)

    # Pause vacuum
    with pytest.raises(HomeAssistantError):
        await common.async_pause(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # Stop vacuum
    with pytest.raises(HomeAssistantError):
        await common.async_stop(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # Return vacuum to base
    with pytest.raises(HomeAssistantError):
        await common.async_return_to_base(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # Spot cleaning
    with pytest.raises(HomeAssistantError):
        await common.async_clean_spot(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # Locate vacuum
    with pytest.raises(HomeAssistantError):
        await common.async_locate(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # Set fan's speed
    with pytest.raises(HomeAssistantError):
        await common.async_set_fan_speed(hass, "medium", _TEST_VACUUM)
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN, None)


async def test_state_services(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test state services."""
    await _register_components(hass)

    # Start vacuum
    await common.async_start(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_SELECT).state == VacuumActivity.CLEANING
    _verify(hass, VacuumActivity.CLEANING, None)
    assert len(calls) == 1
    assert calls[-1].data["action"] == "start"
    assert calls[-1].data["caller"] == _TEST_VACUUM

    # Pause vacuum
    await common.async_pause(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_SELECT).state == VacuumActivity.PAUSED
    _verify(hass, VacuumActivity.PAUSED, None)
    assert len(calls) == 2
    assert calls[-1].data["action"] == "pause"
    assert calls[-1].data["caller"] == _TEST_VACUUM

    # Stop vacuum
    await common.async_stop(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_SELECT).state == VacuumActivity.IDLE
    _verify(hass, VacuumActivity.IDLE, None)
    assert len(calls) == 3
    assert calls[-1].data["action"] == "stop"
    assert calls[-1].data["caller"] == _TEST_VACUUM

    # Return vacuum to base
    await common.async_return_to_base(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_SELECT).state == VacuumActivity.RETURNING
    _verify(hass, VacuumActivity.RETURNING, None)
    assert len(calls) == 4
    assert calls[-1].data["action"] == "return_to_base"
    assert calls[-1].data["caller"] == _TEST_VACUUM


async def test_clean_spot_service(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test clean spot service."""
    await _register_components(hass)

    # Clean spot
    await common.async_clean_spot(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_SPOT_CLEANING_INPUT_BOOLEAN).state == STATE_ON
    assert len(calls) == 1
    assert calls[-1].data["action"] == "clean_spot"
    assert calls[-1].data["caller"] == _TEST_VACUUM


async def test_locate_service(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test locate service."""
    await _register_components(hass)

    # Locate vacuum
    await common.async_locate(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_LOCATING_INPUT_BOOLEAN).state == STATE_ON
    assert len(calls) == 1
    assert calls[-1].data["action"] == "locate"
    assert calls[-1].data["caller"] == _TEST_VACUUM


async def test_set_fan_speed(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test set valid fan speed."""
    await _register_components(hass)

    # Set vacuum's fan speed to high
    await common.async_set_fan_speed(hass, "high", _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_FAN_SPEED_INPUT_SELECT).state == "high"
    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_fan_speed"
    assert calls[-1].data["caller"] == _TEST_VACUUM
    assert calls[-1].data["option"] == "high"

    # Set fan's speed to medium
    await common.async_set_fan_speed(hass, "medium", _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_FAN_SPEED_INPUT_SELECT).state == "medium"
    assert len(calls) == 2
    assert calls[-1].data["action"] == "set_fan_speed"
    assert calls[-1].data["caller"] == _TEST_VACUUM
    assert calls[-1].data["option"] == "medium"


async def test_set_invalid_fan_speed(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test set invalid fan speed when fan has valid speed."""
    await _register_components(hass)

    # Set vacuum's fan speed to high
    await common.async_set_fan_speed(hass, "high", _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_FAN_SPEED_INPUT_SELECT).state == "high"

    # Set vacuum's fan speed to 'invalid'
    await common.async_set_fan_speed(hass, "invalid", _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify fan speed is unchanged
    assert hass.states.get(_FAN_SPEED_INPUT_SELECT).state == "high"


def _verify(
    hass: HomeAssistant, expected_state: str, expected_battery_level: int
) -> None:
    """Verify vacuum's state and speed."""
    state = hass.states.get(_TEST_VACUUM)
    attributes = state.attributes
    assert state.state == expected_state
    assert attributes.get(ATTR_BATTERY_LEVEL) == expected_battery_level


async def _register_basic_vacuum(hass: HomeAssistant) -> None:
    """Register basic vacuum with only required options for testing."""
    with assert_setup_component(1, "input_select"):
        assert await setup.async_setup_component(
            hass,
            "input_select",
            {
                "input_select": {
                    "state": {"name": "State", "options": [VacuumActivity.CLEANING]}
                }
            },
        )

    with assert_setup_component(1, "vacuum"):
        assert await setup.async_setup_component(
            hass,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_vacuum": {
                            "start": {
                                "service": "input_select.select_option",
                                "data": {
                                    "entity_id": _STATE_INPUT_SELECT,
                                    "option": VacuumActivity.CLEANING,
                                },
                            }
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def _register_components(hass: HomeAssistant) -> None:
    """Register basic components for testing."""
    with assert_setup_component(2, "input_boolean"):
        assert await setup.async_setup_component(
            hass,
            "input_boolean",
            {"input_boolean": {"spot_cleaning": None, "locating": None}},
        )

    with assert_setup_component(2, "input_select"):
        assert await setup.async_setup_component(
            hass,
            "input_select",
            {
                "input_select": {
                    "state": {
                        "name": "State",
                        "options": [
                            VacuumActivity.CLEANING,
                            VacuumActivity.DOCKED,
                            VacuumActivity.IDLE,
                            VacuumActivity.PAUSED,
                            VacuumActivity.RETURNING,
                        ],
                    },
                    "fan_speed": {
                        "name": "Fan speed",
                        "options": ["", "low", "medium", "high"],
                    },
                }
            },
        )

    with assert_setup_component(1, "vacuum"):
        test_vacuum_config = {
            "value_template": "{{ states('input_select.state') }}",
            "fan_speed_template": "{{ states('input_select.fan_speed') }}",
            "start": [
                {
                    "service": "input_select.select_option",
                    "data": {
                        "entity_id": _STATE_INPUT_SELECT,
                        "option": VacuumActivity.CLEANING,
                    },
                },
                {
                    "service": "test.automation",
                    "data_template": {
                        "action": "start",
                        "caller": "{{ this.entity_id }}",
                    },
                },
            ],
            "pause": [
                {
                    "service": "input_select.select_option",
                    "data": {
                        "entity_id": _STATE_INPUT_SELECT,
                        "option": VacuumActivity.PAUSED,
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
            "stop": [
                {
                    "service": "input_select.select_option",
                    "data": {
                        "entity_id": _STATE_INPUT_SELECT,
                        "option": VacuumActivity.IDLE,
                    },
                },
                {
                    "service": "test.automation",
                    "data_template": {
                        "action": "stop",
                        "caller": "{{ this.entity_id }}",
                    },
                },
            ],
            "return_to_base": [
                {
                    "service": "input_select.select_option",
                    "data": {
                        "entity_id": _STATE_INPUT_SELECT,
                        "option": VacuumActivity.RETURNING,
                    },
                },
                {
                    "service": "test.automation",
                    "data_template": {
                        "action": "return_to_base",
                        "caller": "{{ this.entity_id }}",
                    },
                },
            ],
            "clean_spot": [
                {
                    "service": "input_boolean.turn_on",
                    "entity_id": _SPOT_CLEANING_INPUT_BOOLEAN,
                },
                {
                    "service": "test.automation",
                    "data_template": {
                        "action": "clean_spot",
                        "caller": "{{ this.entity_id }}",
                    },
                },
            ],
            "locate": [
                {
                    "service": "input_boolean.turn_on",
                    "entity_id": _LOCATING_INPUT_BOOLEAN,
                },
                {
                    "service": "test.automation",
                    "data_template": {
                        "action": "locate",
                        "caller": "{{ this.entity_id }}",
                    },
                },
            ],
            "set_fan_speed": [
                {
                    "service": "input_select.select_option",
                    "data_template": {
                        "entity_id": _FAN_SPEED_INPUT_SELECT,
                        "option": "{{ fan_speed }}",
                    },
                },
                {
                    "service": "test.automation",
                    "data_template": {
                        "action": "set_fan_speed",
                        "caller": "{{ this.entity_id }}",
                        "option": "{{ fan_speed }}",
                    },
                },
            ],
            "fan_speeds": ["low", "medium", "high"],
            "attribute_templates": {
                "test_attribute": "It {{ states.sensor.test_state.state }}."
            },
        }

        assert await setup.async_setup_component(
            hass,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {"test_vacuum": test_vacuum_config},
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()
