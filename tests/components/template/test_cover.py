"""The tests the cover command line platform."""
import logging

import pytest

from homeassistant import setup
from homeassistant.components.cover import ATTR_POSITION, ATTR_TILT_POSITION, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_TOGGLE,
    SERVICE_TOGGLE_COVER_TILT,
    STATE_CLOSED,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_UNAVAILABLE,
)

from tests.common import assert_setup_component, async_mock_service

_LOGGER = logging.getLogger(__name__)

ENTITY_COVER = "cover.test_template_cover"


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_template_state_text(hass, calls):
    """Test the state text of a template."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "value_template": "{{ states.cover.test_state.state }}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.async_set("cover.test_state", STATE_OPEN)
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_OPEN

    state = hass.states.async_set("cover.test_state", STATE_CLOSED)
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_CLOSED


async def test_template_state_boolean(hass, calls):
    """Test the value_template attribute."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "value_template": "{{ 1 == 1 }}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_OPEN


async def test_template_position(hass, calls):
    """Test the position_template attribute."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "position_template": "{{ states.cover.test.attributes.position }}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test",
                            },
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.async_set("cover.test", STATE_CLOSED)
    await hass.async_block_till_done()

    entity = hass.states.get("cover.test")
    attrs = {}
    attrs["position"] = 42
    hass.states.async_set(entity.entity_id, entity.state, attributes=attrs)
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") == 42.0
    assert state.state == STATE_OPEN

    state = hass.states.async_set("cover.test", STATE_OPEN)
    await hass.async_block_till_done()
    entity = hass.states.get("cover.test")
    attrs["position"] = 0.0
    hass.states.async_set(entity.entity_id, entity.state, attributes=attrs)
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") == 0.0
    assert state.state == STATE_CLOSED


async def test_template_tilt(hass, calls):
    """Test the tilt_template attribute."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "value_template": "{{ 1 == 1 }}",
                            "tilt_template": "{{ 42 }}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_tilt_position") == 42.0


async def test_template_out_of_bounds(hass, calls):
    """Test template out-of-bounds condition."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "position_template": "{{ -1 }}",
                            "tilt_template": "{{ 110 }}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_tilt_position") is None
    assert state.attributes.get("current_position") is None


async def test_template_mutex(hass, calls):
    """Test that only value or position template can be used."""
    with assert_setup_component(0, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "value_template": "{{ 1 == 1 }}",
                            "position_template": "{{ 42 }}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                            "icon_template": "{% if states.cover.test_state.state %}"
                            "mdi:check"
                            "{% endif %}",
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_template_open_or_position(hass, caplog):
    """Test that at least one of open_cover or set_position is used."""
    assert await setup.async_setup_component(
        hass,
        "cover",
        {
            "cover": {
                "platform": "template",
                "covers": {"test_template_cover": {"value_template": "{{ 1 == 1 }}"}},
            }
        },
    )
    await hass.async_block_till_done()

    assert hass.states.async_all() == []
    assert "Invalid config for [cover.template]" in caplog.text


async def test_template_open_and_close(hass, calls):
    """Test that if open_cover is specified, close_cover is too."""
    with assert_setup_component(0, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "value_template": "{{ 1 == 1 }}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_template_non_numeric(hass, calls):
    """Test that tilt_template values are numeric."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "position_template": "{{ on }}",
                            "tilt_template": "{% if states.cover.test_state.state %}"
                            "on"
                            "{% else %}"
                            "off"
                            "{% endif %}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_tilt_position") is None
    assert state.attributes.get("current_position") is None


async def test_open_action(hass, calls):
    """Test the open_cover command."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "position_template": "{{ 0 }}",
                            "open_cover": {"service": "test.automation"},
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_CLOSED

    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_close_stop_action(hass, calls):
    """Test the close-cover and stop_cover commands."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "position_template": "{{ 100 }}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {"service": "test.automation"},
                            "stop_cover": {"service": "test.automation"},
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_OPEN

    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()

    assert len(calls) == 2


async def test_set_position(hass, calls):
    """Test the set_position command."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "input_number",
            {"input_number": {"test": {"min": "0", "max": "100", "initial": "42"}}},
        )
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "position_template": "{{ states.input_number.test.state | int }}",
                            "set_cover_position": {
                                "service": "input_number.set_value",
                                "entity_id": "input_number.test",
                                "data_template": {"value": "{{ position }}"},
                            },
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.async_set("input_number.test", 42)
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_OPEN

    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") == 100.0

    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") == 0.0

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") == 100.0

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") == 0.0

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_POSITION: 25},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") == 25.0


async def test_set_tilt_position(hass, calls):
    """Test the set_tilt_position command."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "position_template": "{{ 100 }}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                            "set_cover_tilt_position": {"service": "test.automation"},
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_TILT_POSITION: 42},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_open_tilt_action(hass, calls):
    """Test the open_cover_tilt command."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "position_template": "{{ 100 }}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                            "set_cover_tilt_position": {"service": "test.automation"},
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_close_tilt_action(hass, calls):
    """Test the close_cover_tilt command."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "position_template": "{{ 100 }}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                            "set_cover_tilt_position": {"service": "test.automation"},
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_set_position_optimistic(hass, calls):
    """Test optimistic position mode."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "set_cover_position": {"service": "test.automation"}
                        }
                    },
                }
            },
        )
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") is None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_POSITION: 42},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") == 42.0

    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_CLOSED

    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_OPEN

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_CLOSED

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_OPEN


async def test_set_tilt_position_optimistic(hass, calls):
    """Test the optimistic tilt_position mode."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "position_template": "{{ 100 }}",
                            "set_cover_position": {"service": "test.automation"},
                            "set_cover_tilt_position": {"service": "test.automation"},
                        }
                    },
                }
            },
        )
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_tilt_position") is None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_TILT_POSITION: 42},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_tilt_position") == 42.0

    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_tilt_position") == 0.0

    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_tilt_position") == 100.0

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_tilt_position") == 0.0

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_tilt_position") == 100.0


async def test_icon_template(hass, calls):
    """Test icon template."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "value_template": "{{ states.cover.test_state.state }}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                            "icon_template": "{% if states.cover.test_state.state %}"
                            "mdi:check"
                            "{% endif %}",
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("icon") == ""

    state = hass.states.async_set("cover.test_state", STATE_OPEN)
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")

    assert state.attributes["icon"] == "mdi:check"


async def test_entity_picture_template(hass, calls):
    """Test icon template."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "value_template": "{{ states.cover.test_state.state }}",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                            "entity_picture_template": "{% if states.cover.test_state.state %}"
                            "/local/cover.png"
                            "{% endif %}",
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("entity_picture") == ""

    state = hass.states.async_set("cover.test_state", STATE_OPEN)
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")

    assert state.attributes["entity_picture"] == "/local/cover.png"


async def test_availability_template(hass, calls):
    """Test availability template."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "value_template": "open",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                            "availability_template": "{{ is_state('availability_state.state','on') }}",
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("availability_state.state", STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get("cover.test_template_cover").state == STATE_UNAVAILABLE

    hass.states.async_set("availability_state.state", STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get("cover.test_template_cover").state != STATE_UNAVAILABLE


async def test_availability_without_availability_template(hass, calls):
    """Test that component is available if there is no."""
    assert await setup.async_setup_component(
        hass,
        "cover",
        {
            "cover": {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        "value_template": "open",
                        "open_cover": {
                            "service": "cover.open_cover",
                            "entity_id": "cover.test_state",
                        },
                        "close_cover": {
                            "service": "cover.close_cover",
                            "entity_id": "cover.test_state",
                        },
                    }
                },
            }
        },
    )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.state != STATE_UNAVAILABLE


async def test_invalid_availability_template_keeps_component_available(hass, caplog):
    """Test that an invalid availability keeps the device available."""
    assert await setup.async_setup_component(
        hass,
        "cover",
        {
            "cover": {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        "availability_template": "{{ x - 12 }}",
                        "value_template": "open",
                        "open_cover": {
                            "service": "cover.open_cover",
                            "entity_id": "cover.test_state",
                        },
                        "close_cover": {
                            "service": "cover.close_cover",
                            "entity_id": "cover.test_state",
                        },
                    }
                },
            }
        },
    )

    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("cover.test_template_cover") != STATE_UNAVAILABLE
    assert ("UndefinedError: 'x' is undefined") in caplog.text


async def test_device_class(hass, calls):
    """Test device class."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "value_template": "{{ states.cover.test_state.state }}",
                            "device_class": "door",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("device_class") == "door"


async def test_invalid_device_class(hass, calls):
    """Test device class."""
    with assert_setup_component(0, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "value_template": "{{ states.cover.test_state.state }}",
                            "device_class": "barnacle_bill",
                            "open_cover": {
                                "service": "cover.open_cover",
                                "entity_id": "cover.test_state",
                            },
                            "close_cover": {
                                "service": "cover.close_cover",
                                "entity_id": "cover.test_state",
                            },
                        }
                    },
                }
            },
        )

    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")
    assert not state
