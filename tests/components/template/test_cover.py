"""The tests for the Template cover platform."""
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
    STATE_CLOSING,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from tests.common import assert_setup_component

ENTITY_COVER = "cover.test_template_cover"


OPEN_CLOSE_COVER_CONFIG = {
    "open_cover": {
        "service": "test.automation",
        "data_template": {
            "action": "open_cover",
            "caller": "{{ this.entity_id }}",
        },
    },
    "close_cover": {
        "service": "test.automation",
        "data_template": {
            "action": "close_cover",
            "caller": "{{ this.entity_id }}",
        },
    },
}


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    ("config", "states"),
    [
        (
            {
                DOMAIN: {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            **OPEN_CLOSE_COVER_CONFIG,
                            "value_template": "{{ states.cover.test_state.state }}",
                        }
                    },
                }
            },
            [
                ("cover.test_state", STATE_OPEN, STATE_OPEN, {}, -1, ""),
                ("cover.test_state", STATE_CLOSED, STATE_CLOSED, {}, -1, ""),
                ("cover.test_state", STATE_OPENING, STATE_OPENING, {}, -1, ""),
                ("cover.test_state", STATE_CLOSING, STATE_CLOSING, {}, -1, ""),
                (
                    "cover.test_state",
                    "dog",
                    STATE_UNKNOWN,
                    {},
                    -1,
                    "Received invalid cover is_on state: dog",
                ),
                ("cover.test_state", STATE_OPEN, STATE_OPEN, {}, -1, ""),
                (
                    "cover.test_state",
                    "cat",
                    STATE_UNKNOWN,
                    {},
                    -1,
                    "Received invalid cover is_on state: cat",
                ),
                ("cover.test_state", STATE_CLOSED, STATE_CLOSED, {}, -1, ""),
                (
                    "cover.test_state",
                    "bear",
                    STATE_UNKNOWN,
                    {},
                    -1,
                    "Received invalid cover is_on state: bear",
                ),
            ],
        ),
        (
            {
                DOMAIN: {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            **OPEN_CLOSE_COVER_CONFIG,
                            "position_template": (
                                "{{ states.cover.test.attributes.position }}"
                            ),
                            "value_template": "{{ states.cover.test_state.state }}",
                        }
                    },
                }
            },
            [
                ("cover.test_state", STATE_OPEN, STATE_UNKNOWN, {}, -1, ""),
                ("cover.test_state", STATE_CLOSED, STATE_UNKNOWN, {}, -1, ""),
                ("cover.test_state", STATE_OPENING, STATE_OPENING, {}, -1, ""),
                ("cover.test_state", STATE_CLOSING, STATE_CLOSING, {}, -1, ""),
                ("cover.test", STATE_CLOSED, STATE_CLOSING, {"position": 0}, 0, ""),
                ("cover.test_state", STATE_OPEN, STATE_CLOSED, {}, -1, ""),
                ("cover.test", STATE_CLOSED, STATE_OPEN, {"position": 10}, 10, ""),
                (
                    "cover.test_state",
                    "dog",
                    STATE_OPEN,
                    {},
                    -1,
                    "Received invalid cover is_on state: dog",
                ),
            ],
        ),
    ],
)
async def test_template_state_text(
    hass: HomeAssistant, states, start_ha, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the state text of a template."""
    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_UNKNOWN

    for entity, set_state, test_state, attr, pos, text in states:
        hass.states.async_set(entity, set_state, attributes=attr)
        await hass.async_block_till_done()
        state = hass.states.get("cover.test_template_cover")
        assert state.state == test_state
        if pos >= 0:
            assert state.attributes.get("current_position") == pos
        assert text in caplog.text


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "value_template": "{{ 1 == 1 }}",
                    }
                },
            }
        },
    ],
)
async def test_template_state_boolean(hass: HomeAssistant, start_ha) -> None:
    """Test the value_template attribute."""
    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_OPEN


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "position_template": (
                            "{{ states.cover.test.attributes.position }}"
                        ),
                    }
                },
            }
        },
    ],
)
async def test_template_position(hass: HomeAssistant, start_ha) -> None:
    """Test the position_template attribute."""
    hass.states.async_set("cover.test", STATE_OPEN)
    attrs = {}

    for set_state, pos, test_state in [
        (STATE_CLOSED, 42, STATE_OPEN),
        (STATE_OPEN, 0.0, STATE_CLOSED),
    ]:
        attrs["position"] = pos
        hass.states.async_set("cover.test", set_state, attributes=attrs)
        await hass.async_block_till_done()
        state = hass.states.get("cover.test_template_cover")
        assert state.attributes.get("current_position") == pos
        assert state.state == test_state


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "optimistic": False,
                    }
                },
            }
        },
    ],
)
async def test_template_not_optimistic(hass, start_ha):
    """Test the is_closed attribute."""
    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "value_template": "{{ 1 == 1 }}",
                        "tilt_template": "{{ 42 }}",
                    }
                },
            }
        },
    ],
)
async def test_template_tilt(hass: HomeAssistant, start_ha) -> None:
    """Test the tilt_template attribute."""
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_tilt_position") == 42.0


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "position_template": "{{ -1 }}",
                        "tilt_template": "{{ 110 }}",
                    }
                },
            }
        },
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "position_template": "{{ on }}",
                        "tilt_template": (
                            "{% if states.cover.test_state.state %}"
                            "on"
                            "{% else %}"
                            "off"
                            "{% endif %}"
                        ),
                    },
                },
            }
        },
    ],
)
async def test_template_out_of_bounds(hass: HomeAssistant, start_ha) -> None:
    """Test template out-of-bounds condition."""
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_tilt_position") is None
    assert state.attributes.get("current_position") is None


@pytest.mark.parametrize(("count", "domain"), [(0, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {"test_template_cover": {"value_template": "{{ 1 == 1 }}"}},
            }
        },
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        "value_template": "{{ 1 == 1 }}",
                        "open_cover": {
                            "service": "test.automation",
                            "data_template": {
                                "action": "open_cover",
                                "caller": "{{ this.entity_id }}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_template_open_or_position(
    hass: HomeAssistant, start_ha, caplog_setup_text
) -> None:
    """Test that at least one of open_cover or set_position is used."""
    assert hass.states.async_all("cover") == []
    assert "Invalid config for [cover.template]" in caplog_setup_text


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "position_template": "{{ 0 }}",
                    }
                },
            }
        },
    ],
)
async def test_open_action(hass: HomeAssistant, start_ha, calls) -> None:
    """Test the open_cover command."""
    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_CLOSED

    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "open_cover"
    assert calls[0].data["caller"] == "cover.test_template_cover"


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "position_template": "{{ 100 }}",
                        "stop_cover": {
                            "service": "test.automation",
                            "data_template": {
                                "action": "stop_cover",
                                "caller": "{{ this.entity_id }}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_close_stop_action(hass: HomeAssistant, start_ha, calls) -> None:
    """Test the close-cover and stop_cover commands."""
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
    assert calls[0].data["action"] == "close_cover"
    assert calls[0].data["caller"] == "cover.test_template_cover"
    assert calls[1].data["action"] == "stop_cover"
    assert calls[1].data["caller"] == "cover.test_template_cover"


@pytest.mark.parametrize(("count", "domain"), [(1, "input_number")])
@pytest.mark.parametrize(
    "config",
    [
        {"input_number": {"test": {"min": "0", "max": "100", "initial": "42"}}},
    ],
)
async def test_set_position(hass: HomeAssistant, start_ha, calls) -> None:
    """Test the set_position command."""
    with assert_setup_component(1, "cover"):
        assert await setup.async_setup_component(
            hass,
            "cover",
            {
                "cover": {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            "set_cover_position": {
                                "service": "test.automation",
                                "data_template": {
                                    "action": "set_cover_position",
                                    "caller": "{{ this.entity_id }}",
                                    "position": "{{ position }}",
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

    state = hass.states.async_set("input_number.test", 42)
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") == 100.0
    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_cover_position"
    assert calls[-1].data["caller"] == "cover.test_template_cover"
    assert calls[-1].data["position"] == 100

    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") == 0.0
    assert len(calls) == 2
    assert calls[-1].data["action"] == "set_cover_position"
    assert calls[-1].data["caller"] == "cover.test_template_cover"
    assert calls[-1].data["position"] == 0

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") == 100.0
    assert len(calls) == 3
    assert calls[-1].data["action"] == "set_cover_position"
    assert calls[-1].data["caller"] == "cover.test_template_cover"
    assert calls[-1].data["position"] == 100

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") == 0.0
    assert len(calls) == 4
    assert calls[-1].data["action"] == "set_cover_position"
    assert calls[-1].data["caller"] == "cover.test_template_cover"
    assert calls[-1].data["position"] == 0

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_POSITION: 25},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("current_position") == 25.0
    assert len(calls) == 5
    assert calls[-1].data["action"] == "set_cover_position"
    assert calls[-1].data["caller"] == "cover.test_template_cover"
    assert calls[-1].data["position"] == 25


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "set_cover_tilt_position": {
                            "service": "test.automation",
                            "data_template": {
                                "action": "set_cover_tilt_position",
                                "caller": "{{ this.entity_id }}",
                                "tilt_position": "{{ tilt }}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
@pytest.mark.parametrize(
    ("service", "attr", "tilt_position"),
    [
        (
            SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_TILT_POSITION: 42},
            42,
        ),
        (SERVICE_OPEN_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, 100),
        (SERVICE_CLOSE_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, 0),
    ],
)
async def test_set_tilt_position(
    hass: HomeAssistant, service, attr, start_ha, calls, tilt_position
) -> None:
    """Test the set_tilt_position command."""
    await hass.services.async_call(
        DOMAIN,
        service,
        attr,
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_cover_tilt_position"
    assert calls[-1].data["caller"] == "cover.test_template_cover"
    assert calls[-1].data["tilt_position"] == tilt_position


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        "set_cover_position": {"service": "test.automation"}
                    }
                },
            }
        },
    ],
)
async def test_set_position_optimistic(hass: HomeAssistant, start_ha, calls) -> None:
    """Test optimistic position mode."""
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

    for service, test_state in [
        (SERVICE_CLOSE_COVER, STATE_CLOSED),
        (SERVICE_OPEN_COVER, STATE_OPEN),
        (SERVICE_TOGGLE, STATE_CLOSED),
        (SERVICE_TOGGLE, STATE_OPEN),
    ]:
        await hass.services.async_call(
            DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
        )
        await hass.async_block_till_done()
        state = hass.states.get("cover.test_template_cover")
        assert state.state == test_state


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
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
    ],
)
async def test_set_tilt_position_optimistic(
    hass: HomeAssistant, start_ha, calls
) -> None:
    """Test the optimistic tilt_position mode."""
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

    for service, pos in [
        (SERVICE_CLOSE_COVER_TILT, 0.0),
        (SERVICE_OPEN_COVER_TILT, 100.0),
        (SERVICE_TOGGLE_COVER_TILT, 0.0),
        (SERVICE_TOGGLE_COVER_TILT, 100.0),
    ]:
        await hass.services.async_call(
            DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
        )
        await hass.async_block_till_done()
        state = hass.states.get("cover.test_template_cover")
        assert state.attributes.get("current_tilt_position") == pos


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "value_template": "{{ states.cover.test_state.state }}",
                        "icon_template": (
                            "{% if states.cover.test_state.state %}mdi:check{% endif %}"
                        ),
                    }
                },
            }
        },
    ],
)
async def test_icon_template(hass: HomeAssistant, start_ha) -> None:
    """Test icon template."""
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("icon") == ""

    state = hass.states.async_set("cover.test_state", STATE_OPEN)
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")

    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "value_template": "{{ states.cover.test_state.state }}",
                        "entity_picture_template": (
                            "{% if states.cover.test_state.state %}"
                            "/local/cover.png"
                            "{% endif %}"
                        ),
                    }
                },
            }
        },
    ],
)
async def test_entity_picture_template(hass: HomeAssistant, start_ha) -> None:
    """Test icon template."""
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("entity_picture") == ""

    state = hass.states.async_set("cover.test_state", STATE_OPEN)
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_template_cover")

    assert state.attributes["entity_picture"] == "/local/cover.png"


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "value_template": "open",
                        "availability_template": (
                            "{{ is_state('availability_state.state','on') }}"
                        ),
                    }
                },
            }
        },
    ],
)
async def test_availability_template(hass: HomeAssistant, start_ha) -> None:
    """Test availability template."""
    hass.states.async_set("availability_state.state", STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get("cover.test_template_cover").state == STATE_UNAVAILABLE

    hass.states.async_set("availability_state.state", STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get("cover.test_template_cover").state != STATE_UNAVAILABLE


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "value_template": "open",
                    }
                },
            }
        },
    ],
)
async def test_availability_without_availability_template(
    hass: HomeAssistant, start_ha
) -> None:
    """Test that component is available if there is no."""
    state = hass.states.get("cover.test_template_cover")
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "availability_template": "{{ x - 12 }}",
                        "value_template": "open",
                    }
                },
            }
        },
    ],
)
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, start_ha, caplog_setup_text
) -> None:
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get("cover.test_template_cover") != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog_setup_text


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "value_template": "{{ states.cover.test_state.state }}",
                        "device_class": "door",
                    }
                },
            }
        },
    ],
)
async def test_device_class(hass: HomeAssistant, start_ha) -> None:
    """Test device class."""
    state = hass.states.get("cover.test_template_cover")
    assert state.attributes.get("device_class") == "door"


@pytest.mark.parametrize(("count", "domain"), [(0, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "value_template": "{{ states.cover.test_state.state }}",
                        "device_class": "barnacle_bill",
                    }
                },
            }
        },
    ],
)
async def test_invalid_device_class(hass: HomeAssistant, start_ha) -> None:
    """Test device class."""
    state = hass.states.get("cover.test_template_cover")
    assert not state


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "test_template_cover_01": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ true }}",
                    },
                    "test_template_cover_02": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ false }}",
                    },
                },
            }
        },
    ],
)
async def test_unique_id(hass: HomeAssistant, start_ha) -> None:
    """Test unique_id option only creates one cover per id."""
    assert len(hass.states.async_all()) == 1


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "garage_door": {
                        **OPEN_CLOSE_COVER_CONFIG,
                        "friendly_name": "Garage Door",
                        "value_template": (
                            "{{ is_state('binary_sensor.garage_door_sensor', 'off') }}"
                        ),
                    },
                },
            }
        },
    ],
)
async def test_state_gets_lowercased(hass: HomeAssistant, start_ha) -> None:
    """Test True/False is lowercased."""

    hass.states.async_set("binary_sensor.garage_door_sensor", "off")
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("cover.garage_door").state == STATE_OPEN
    hass.states.async_set("binary_sensor.garage_door_sensor", "on")
    await hass.async_block_till_done()
    assert hass.states.get("cover.garage_door").state == STATE_CLOSED


@pytest.mark.parametrize(("count", "domain"), [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "covers": {
                    "office": {
                        "icon_template": """{% if is_state('cover.office', 'open') %}
            mdi:window-shutter-open
          {% else %}
            mdi:window-shutter
          {% endif %}""",
                        "open_cover": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.office_blinds_up",
                        },
                        "close_cover": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.office_blinds_down",
                        },
                        "stop_cover": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.office_blinds_up",
                        },
                    },
                },
            }
        },
    ],
)
async def test_self_referencing_icon_with_no_template_is_not_a_loop(
    hass: HomeAssistant, start_ha, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a self referencing icon with no value template is not a loop."""
    assert len(hass.states.async_all()) == 1

    assert "Template loop detected" not in caplog.text
