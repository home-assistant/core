"""The tests for the Template cover platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import cover, template
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverEntityFeature,
    CoverState,
)
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
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import ConfigurationStyle, async_get_flow_preview_state

from tests.common import MockConfigEntry, assert_setup_component
from tests.typing import WebSocketGenerator

TEST_OBJECT_ID = "test_template_cover"
TEST_ENTITY_ID = f"cover.{TEST_OBJECT_ID}"
TEST_STATE_ENTITY_ID = "cover.test_state"

TEST_STATE_TRIGGER = {
    "trigger": {
        "trigger": "state",
        "entity_id": [
            "cover.test_state",
            "cover.test_position",
            "binary_sensor.garage_door_sensor",
        ],
    },
    "variables": {"triggering_entity": "{{ trigger.entity_id }}"},
    "action": [
        {"event": "action_event", "event_data": {"what": "{{ triggering_entity}}"}}
    ],
}


OPEN_COVER = {
    "service": "test.automation",
    "data_template": {
        "action": "open_cover",
        "caller": "{{ this.entity_id }}",
    },
}

CLOSE_COVER = {
    "service": "test.automation",
    "data_template": {
        "action": "close_cover",
        "caller": "{{ this.entity_id }}",
    },
}

SET_COVER_POSITION = {
    "service": "test.automation",
    "data_template": {
        "action": "set_cover_position",
        "caller": "{{ this.entity_id }}",
        "position": "{{ position }}",
    },
}

SET_COVER_TILT_POSITION = {
    "service": "test.automation",
    "data_template": {
        "action": "set_cover_tilt_position",
        "caller": "{{ this.entity_id }}",
        "tilt_position": "{{ tilt }}",
    },
}

COVER_ACTIONS = {
    "open_cover": OPEN_COVER,
    "close_cover": CLOSE_COVER,
}
NAMED_COVER_ACTIONS = {
    **COVER_ACTIONS,
    "name": TEST_OBJECT_ID,
}
UNIQUE_ID_CONFIG = {
    **COVER_ACTIONS,
    "unique_id": "not-so-unique-anymore",
}


async def async_setup_legacy_format(
    hass: HomeAssistant, count: int, cover_config: dict[str, Any]
) -> None:
    """Do setup of cover integration via legacy format."""
    config = {"cover": {"platform": "template", "covers": cover_config}}

    with assert_setup_component(count, cover.DOMAIN):
        assert await async_setup_component(
            hass,
            cover.DOMAIN,
            config,
        )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_modern_format(
    hass: HomeAssistant, count: int, cover_config: dict[str, Any]
) -> None:
    """Do setup of cover integration via modern format."""
    config = {"template": {"cover": cover_config}}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_trigger_format(
    hass: HomeAssistant, count: int, cover_config: dict[str, Any]
) -> None:
    """Do setup of cover integration via trigger format."""
    config = {"template": {**TEST_STATE_TRIGGER, "cover": cover_config}}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_cover_config(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    cover_config: dict[str, Any],
) -> None:
    """Do setup of cover integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(hass, count, cover_config)
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(hass, count, cover_config)
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(hass, count, cover_config)


@pytest.fixture
async def setup_cover(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    cover_config: dict[str, Any],
) -> None:
    """Do setup of cover integration."""
    await async_setup_cover_config(hass, count, style, cover_config)


@pytest.fixture
async def setup_state_cover(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
):
    """Do setup of cover integration using a state template."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    **COVER_ACTIONS,
                    "value_template": state_template,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                **NAMED_COVER_ACTIONS,
                "state": state_template,
            },
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(
            hass,
            count,
            {
                **NAMED_COVER_ACTIONS,
                "state": state_template,
            },
        )


@pytest.fixture
async def setup_position_cover(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    position_template: str,
):
    """Do setup of cover integration using a state template."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    **COVER_ACTIONS,
                    "set_cover_position": SET_COVER_POSITION,
                    "position_template": position_template,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                **NAMED_COVER_ACTIONS,
                "set_cover_position": SET_COVER_POSITION,
                "position": position_template,
            },
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(
            hass,
            count,
            {
                **NAMED_COVER_ACTIONS,
                "set_cover_position": SET_COVER_POSITION,
                "position": position_template,
            },
        )


@pytest.fixture
async def setup_single_attribute_state_cover(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
    attribute: str,
    attribute_template: str,
) -> None:
    """Do setup of cover integration testing a single attribute."""
    extra = {attribute: attribute_template} if attribute and attribute_template else {}
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    **COVER_ACTIONS,
                    "value_template": state_template,
                    **extra,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                **NAMED_COVER_ACTIONS,
                "state": state_template,
                **extra,
            },
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(
            hass,
            count,
            {
                **NAMED_COVER_ACTIONS,
                "state": state_template,
                **extra,
            },
        )


@pytest.fixture
async def setup_empty_action(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    script: str,
):
    """Do setup of cover integration using a empty actions template."""
    empty = {
        "open_cover": [],
        "close_cover": [],
        script: [],
    }
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {TEST_OBJECT_ID: empty},
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {"name": TEST_OBJECT_ID, **empty},
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(
            hass,
            count,
            {"name": TEST_OBJECT_ID, **empty},
        )


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states.cover.test_state.state }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("set_state", "test_state", "text"),
    [
        (CoverState.OPEN, CoverState.OPEN, ""),
        (CoverState.CLOSED, CoverState.CLOSED, ""),
        (CoverState.OPENING, CoverState.OPENING, ""),
        (CoverState.CLOSING, CoverState.CLOSING, ""),
        ("dog", STATE_UNKNOWN, "Received invalid cover is_on state: dog"),
        ("cat", STATE_UNKNOWN, "Received invalid cover is_on state: cat"),
        ("bear", STATE_UNKNOWN, "Received invalid cover is_on state: bear"),
    ],
)
@pytest.mark.usefixtures("setup_state_cover")
async def test_template_state_text(
    hass: HomeAssistant,
    set_state: str,
    test_state: str,
    text: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the state text of a template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(TEST_STATE_ENTITY_ID, set_state)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == test_state
    assert text in caplog.text


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("state_template", "expected"),
    [
        ("{{ 'open' }}", CoverState.OPEN),
        ("{{ 'closed' }}", CoverState.CLOSED),
        ("{{ 'opening' }}", CoverState.OPENING),
        ("{{ 'closing' }}", CoverState.CLOSING),
        ("{{ 'dog' }}", STATE_UNKNOWN),
        ("{{ x - 1 }}", STATE_UNAVAILABLE),
    ],
)
@pytest.mark.usefixtures("setup_state_cover")
async def test_template_state_states(
    hass: HomeAssistant,
    expected: str,
) -> None:
    """Test state template states."""

    hass.states.async_set(TEST_STATE_ENTITY_ID, None)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == expected


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states.cover.test_state.state }}",
            "{{ states.cover.test_position.attributes.position }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "position_template"),
        (ConfigurationStyle.MODERN, "position"),
        (ConfigurationStyle.TRIGGER, "position"),
    ],
)
@pytest.mark.parametrize(
    "states",
    [
        (
            [
                (TEST_STATE_ENTITY_ID, CoverState.OPEN, STATE_UNKNOWN, "", None),
                (TEST_STATE_ENTITY_ID, CoverState.CLOSED, STATE_UNKNOWN, "", None),
                (
                    TEST_STATE_ENTITY_ID,
                    CoverState.OPENING,
                    CoverState.OPENING,
                    "",
                    None,
                ),
                (
                    TEST_STATE_ENTITY_ID,
                    CoverState.CLOSING,
                    CoverState.CLOSING,
                    "",
                    None,
                ),
                ("cover.test_position", CoverState.CLOSED, CoverState.CLOSING, "", 0),
                (TEST_STATE_ENTITY_ID, CoverState.OPEN, CoverState.CLOSED, "", None),
                ("cover.test_position", CoverState.CLOSED, CoverState.OPEN, "", 10),
                (
                    TEST_STATE_ENTITY_ID,
                    "dog",
                    CoverState.OPEN,
                    "Received invalid cover is_on state: dog",
                    None,
                ),
            ]
        )
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_cover")
async def test_template_state_text_with_position(
    hass: HomeAssistant,
    states: list[tuple[str, str, str, int | None]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the state of a position template in order."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN

    for test_entity, set_state, test_state, text, position in states:
        attrs = {"position": position} if position is not None else {}

        hass.states.async_set(test_entity, set_state, attrs)
        await hass.async_block_till_done()

        state = hass.states.get(TEST_ENTITY_ID)
        assert state.state == test_state
        if position is not None:
            assert state.attributes.get("current_position") == position
        assert text in caplog.text


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states.cover.test_state.state }}",
            "{{ state_attr('cover.test_state', 'position') }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "position_template"),
        (ConfigurationStyle.MODERN, "position"),
        (ConfigurationStyle.TRIGGER, "position"),
    ],
)
@pytest.mark.parametrize(
    "set_state",
    [
        "",
        None,
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_cover")
async def test_template_state_text_ignored_if_none_or_empty(
    hass: HomeAssistant,
    set_state: str,
) -> None:
    """Test ignoring an empty state text of a template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(TEST_STATE_ENTITY_ID, set_state)
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(("count", "state_template"), [(1, "{{ 1 == 1 }}")])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_cover")
async def test_template_state_boolean(hass: HomeAssistant) -> None:
    """Test the value_template attribute."""
    # This forces a trigger for trigger based entities
    hass.states.async_set(TEST_STATE_ENTITY_ID, None)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == CoverState.OPEN


@pytest.mark.parametrize(
    ("count", "position_template"),
    [(1, "{{ states.cover.test_state.attributes.position }}")],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("test_state", "position", "expected"),
    [
        (CoverState.CLOSED, 42, CoverState.OPEN),
        (CoverState.OPEN, 0.0, CoverState.CLOSED),
        (CoverState.CLOSED, None, STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("setup_position_cover")
async def test_template_position(
    hass: HomeAssistant,
    test_state: str,
    position: int | None,
    expected: str,
    caplog: pytest.LogCaptureFixture,
    calls: list[ServiceCall],
) -> None:
    """Test the position_template attribute."""
    hass.states.async_set(TEST_STATE_ENTITY_ID, CoverState.OPEN)
    await hass.async_block_till_done()

    hass.states.async_set(
        TEST_STATE_ENTITY_ID, test_state, attributes={"position": position}
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("current_position") == position
    assert state.state == expected
    assert "ValueError" not in caplog.text

    # Test to make sure optimistic is not set with only a position template.
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, "position": 10},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("current_position") == position
    assert state.state == expected


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "cover_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "test_template_cover": {
                    **COVER_ACTIONS,
                    "optimistic": False,
                }
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                **NAMED_COVER_ACTIONS,
                "optimistic": False,
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                **NAMED_COVER_ACTIONS,
                "optimistic": False,
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_cover")
async def test_template_not_optimistic(
    hass: HomeAssistant,
    calls: list[ServiceCall],
) -> None:
    """Test the is_closed attribute."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN

    # Test to make sure optimistic is not set with only a position template.
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN

    # Test to make sure optimistic is not set with only a position template.
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(("count", "state_template"), [(1, "{{ 1 == 1 }}")])
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (
            ConfigurationStyle.LEGACY,
            "tilt_template",
        ),
        (
            ConfigurationStyle.MODERN,
            "tilt",
        ),
        (
            ConfigurationStyle.TRIGGER,
            "tilt",
        ),
    ],
)
@pytest.mark.parametrize(
    ("attribute_template", "tilt_position"),
    [
        ("{{ 1 }}", 1.0),
        ("{{ 42 }}", 42.0),
        ("{{ 100 }}", 100.0),
        ("{{ None }}", None),
        ("{{ 110 }}", None),
        ("{{ -1 }}", None),
        ("{{ 'on' }}", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_cover")
async def test_template_tilt(hass: HomeAssistant, tilt_position: float | None) -> None:
    """Test tilt in and out-of-bound conditions."""
    # This forces a trigger for trigger based entities
    hass.states.async_set(TEST_STATE_ENTITY_ID, None)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("current_tilt_position") == tilt_position


@pytest.mark.parametrize(("count", "state_template"), [(1, "{{ 1 == 1 }}")])
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (
            ConfigurationStyle.LEGACY,
            "position_template",
        ),
        (
            ConfigurationStyle.MODERN,
            "position",
        ),
        (
            ConfigurationStyle.TRIGGER,
            "position",
        ),
    ],
)
@pytest.mark.parametrize(
    "attribute_template",
    [
        "{{ -1 }}",
        "{{ 110 }}",
        "{{ 'on' }}",
        "{{ 'off' }}",
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_cover")
async def test_position_out_of_bounds(hass: HomeAssistant) -> None:
    """Test position out-of-bounds condition."""
    # This forces a trigger for trigger based entities
    hass.states.async_set(TEST_STATE_ENTITY_ID, None)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("current_position") is None


@pytest.mark.parametrize("count", [0])
@pytest.mark.parametrize(
    ("style", "cover_config", "error"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "test_template_cover": {
                    "value_template": "{{ 1 == 1 }}",
                }
            },
            "Invalid config for 'cover' from integration 'template'",
        ),
        (
            ConfigurationStyle.LEGACY,
            {
                "test_template_cover": {
                    "value_template": "{{ 1 == 1 }}",
                    "open_cover": OPEN_COVER,
                }
            },
            "Invalid config for 'cover' from integration 'template'",
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "name": TEST_OBJECT_ID,
                "state": "{{ 1 == 1 }}",
            },
            "Invalid config for 'template': must contain at least one of open_cover, set_cover_position.",
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "name": TEST_OBJECT_ID,
                "state": "{{ 1 == 1 }}",
                "open_cover": OPEN_COVER,
            },
            "Invalid config for 'template': some but not all values in the same group of inclusion 'open_or_close'",
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "name": TEST_OBJECT_ID,
                "state": "{{ 1 == 1 }}",
            },
            "Invalid config for 'template': must contain at least one of open_cover, set_cover_position.",
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "name": TEST_OBJECT_ID,
                "state": "{{ 1 == 1 }}",
                "open_cover": OPEN_COVER,
            },
            "Invalid config for 'template': some but not all values in the same group of inclusion 'open_or_close'",
        ),
    ],
)
async def test_template_open_or_position(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    cover_config: dict[str, Any],
    error: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that at least one of open_cover or set_position is used."""
    await async_setup_cover_config(hass, count, style, cover_config)
    assert hass.states.async_all("cover") == []
    assert error in caplog.text


@pytest.mark.parametrize(
    ("count", "position_template"),
    [(1, "{{ 0 }}")],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_position_cover")
async def test_open_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test the open_cover command."""

    # This forces a trigger for trigger based entities
    hass.states.async_set(TEST_STATE_ENTITY_ID, None)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == CoverState.CLOSED

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "open_cover"
    assert calls[0].data["caller"] == TEST_ENTITY_ID


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "cover_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "test_template_cover": {
                    **COVER_ACTIONS,
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
        ),
        (
            ConfigurationStyle.MODERN,
            {
                **NAMED_COVER_ACTIONS,
                "position": "{{ 100 }}",
                "stop_cover": {
                    "service": "test.automation",
                    "data_template": {
                        "action": "stop_cover",
                        "caller": "{{ this.entity_id }}",
                    },
                },
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                **NAMED_COVER_ACTIONS,
                "position": "{{ 100 }}",
                "stop_cover": {
                    "service": "test.automation",
                    "data_template": {
                        "action": "stop_cover",
                        "caller": "{{ this.entity_id }}",
                    },
                },
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_cover")
async def test_close_stop_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test the close-cover and stop_cover commands."""
    # This forces a trigger for trigger based entities
    hass.states.async_set(TEST_STATE_ENTITY_ID, None)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == CoverState.OPEN

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(calls) == 2
    assert calls[0].data["action"] == "close_cover"
    assert calls[0].data["caller"] == TEST_ENTITY_ID
    assert calls[1].data["action"] == "stop_cover"
    assert calls[1].data["caller"] == TEST_ENTITY_ID


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "cover_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "test_template_cover": {
                    "set_cover_position": SET_COVER_POSITION,
                }
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "name": TEST_OBJECT_ID,
                "set_cover_position": SET_COVER_POSITION,
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "name": TEST_OBJECT_ID,
                "set_cover_position": SET_COVER_POSITION,
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_cover")
async def test_set_position(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test the set_position command."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("current_position") == 100.0
    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_cover_position"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["position"] == 100

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("current_position") == 0.0
    assert len(calls) == 2
    assert calls[-1].data["action"] == "set_cover_position"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["position"] == 0

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: TEST_ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("current_position") == 100.0
    assert len(calls) == 3
    assert calls[-1].data["action"] == "set_cover_position"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["position"] == 100

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: TEST_ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("current_position") == 0.0
    assert len(calls) == 4
    assert calls[-1].data["action"] == "set_cover_position"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["position"] == 0

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_POSITION: 25},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("current_position") == 25.0
    assert len(calls) == 5
    assert calls[-1].data["action"] == "set_cover_position"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["position"] == 25


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "cover_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "test_template_cover": {
                    **COVER_ACTIONS,
                    "set_cover_tilt_position": SET_COVER_TILT_POSITION,
                }
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                **NAMED_COVER_ACTIONS,
                "set_cover_tilt_position": SET_COVER_TILT_POSITION,
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                **NAMED_COVER_ACTIONS,
                "set_cover_tilt_position": SET_COVER_TILT_POSITION,
            },
        ),
    ],
)
@pytest.mark.parametrize(
    ("service", "attr", "tilt_position"),
    [
        (
            SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_TILT_POSITION: 42},
            42,
        ),
        (SERVICE_OPEN_COVER_TILT, {ATTR_ENTITY_ID: TEST_ENTITY_ID}, 100),
        (SERVICE_CLOSE_COVER_TILT, {ATTR_ENTITY_ID: TEST_ENTITY_ID}, 0),
    ],
)
@pytest.mark.usefixtures("setup_cover")
async def test_set_tilt_position(
    hass: HomeAssistant,
    service,
    attr,
    tilt_position,
    calls: list[ServiceCall],
) -> None:
    """Test the set_tilt_position command."""
    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        attr,
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_cover_tilt_position"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["tilt_position"] == tilt_position


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "cover_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "test_template_cover": {
                    "set_cover_position": SET_COVER_POSITION,
                }
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "name": TEST_OBJECT_ID,
                "set_cover_position": SET_COVER_POSITION,
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "name": TEST_OBJECT_ID,
                "set_cover_position": SET_COVER_POSITION,
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_cover")
async def test_set_position_optimistic(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test optimistic position mode."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("current_position") is None

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_POSITION: 42},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("current_position") == 42.0

    for service, test_state in (
        (SERVICE_CLOSE_COVER, CoverState.CLOSED),
        (SERVICE_OPEN_COVER, CoverState.OPEN),
        (SERVICE_TOGGLE, CoverState.CLOSED),
        (SERVICE_TOGGLE, CoverState.OPEN),
    ):
        await hass.services.async_call(
            COVER_DOMAIN, service, {ATTR_ENTITY_ID: TEST_ENTITY_ID}, blocking=True
        )
        await hass.async_block_till_done()
        state = hass.states.get(TEST_ENTITY_ID)
        assert state.state == test_state


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "cover_config"),
    [
        (
            ConfigurationStyle.TRIGGER,
            {
                "name": TEST_OBJECT_ID,
                "set_cover_position": SET_COVER_POSITION,
                "picture": "{{ 'foo.png' if is_state('cover.test_state', 'open') else 'bar.png' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_cover")
async def test_non_optimistic_template_with_optimistic_state(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test optimistic state with non-optimistic template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert "entity_picture" not in state.attributes

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_POSITION: 42},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == CoverState.OPEN
    assert state.attributes["current_position"] == 42.0
    assert "entity_picture" not in state.attributes

    hass.states.async_set(TEST_STATE_ENTITY_ID, CoverState.OPEN)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == CoverState.OPEN
    assert state.attributes["current_position"] == 42.0
    assert state.attributes["entity_picture"] == "foo.png"


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "cover_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "test_template_cover": {
                    "position_template": "{{ 100 }}",
                    "set_cover_position": SET_COVER_POSITION,
                    "set_cover_tilt_position": SET_COVER_TILT_POSITION,
                }
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "name": TEST_OBJECT_ID,
                "position": "{{ 100 }}",
                "set_cover_position": SET_COVER_POSITION,
                "set_cover_tilt_position": SET_COVER_TILT_POSITION,
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "name": TEST_OBJECT_ID,
                "position": "{{ 100 }}",
                "set_cover_position": SET_COVER_POSITION,
                "set_cover_tilt_position": SET_COVER_TILT_POSITION,
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_cover")
async def test_set_tilt_position_optimistic(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test the optimistic tilt_position mode."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("current_tilt_position") is None

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_TILT_POSITION: 42},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("current_tilt_position") == 42.0

    for service, pos in (
        (SERVICE_CLOSE_COVER_TILT, 0.0),
        (SERVICE_OPEN_COVER_TILT, 100.0),
        (SERVICE_TOGGLE_COVER_TILT, 0.0),
        (SERVICE_TOGGLE_COVER_TILT, 100.0),
    ):
        await hass.services.async_call(
            COVER_DOMAIN, service, {ATTR_ENTITY_ID: TEST_ENTITY_ID}, blocking=True
        )
        await hass.async_block_till_done()
        state = hass.states.get(TEST_ENTITY_ID)
        assert state.attributes.get("current_tilt_position") == pos


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states.cover.test_state.state }}",
            "{% if states.cover.test_state.state %}mdi:check{% endif %}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute", "initial_expected_state"),
    [
        (ConfigurationStyle.LEGACY, "icon_template", ""),
        (ConfigurationStyle.MODERN, "icon", ""),
        (ConfigurationStyle.TRIGGER, "icon", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_cover")
async def test_icon_template(
    hass: HomeAssistant, initial_expected_state: str | None
) -> None:
    """Test icon template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("icon") == initial_expected_state

    state = hass.states.async_set("cover.test_state", CoverState.OPEN)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)

    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states.cover.test_state.state }}",
            "{% if states.cover.test_state.state %}/local/cover.png{% endif %}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute", "initial_expected_state"),
    [
        (ConfigurationStyle.LEGACY, "entity_picture_template", ""),
        (ConfigurationStyle.MODERN, "picture", ""),
        (ConfigurationStyle.TRIGGER, "picture", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_cover")
async def test_entity_picture_template(
    hass: HomeAssistant, initial_expected_state: str | None
) -> None:
    """Test icon template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("entity_picture") == initial_expected_state

    state = hass.states.async_set("cover.test_state", CoverState.OPEN)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)

    assert state.attributes["entity_picture"] == "/local/cover.png"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{{ is_state('availability_state.state','on') }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "availability_template"),
        (ConfigurationStyle.MODERN, "availability"),
        (ConfigurationStyle.TRIGGER, "availability"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_cover")
async def test_availability_template(hass: HomeAssistant) -> None:
    """Test availability template."""
    hass.states.async_set("availability_state.state", STATE_OFF)
    # This forces a trigger for trigger based entities
    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_UNAVAILABLE

    hass.states.async_set("availability_state.state", STATE_ON)
    # This forces a trigger for trigger based entities
    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state != STATE_UNAVAILABLE


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("config", "domain"),
    [
        (
            {
                COVER_DOMAIN: {
                    "platform": "template",
                    "covers": {
                        "test_template_cover": {
                            **COVER_ACTIONS,
                            "availability_template": "{{ x - 12 }}",
                            "value_template": "open",
                        }
                    },
                }
            },
            cover.DOMAIN,
        ),
        (
            {
                "template": {
                    "cover": {
                        **NAMED_COVER_ACTIONS,
                        "state": "{{ true }}",
                        "availability": "{{ x - 12 }}",
                    },
                }
            },
            template.DOMAIN,
        ),
        (
            {
                "template": {
                    **TEST_STATE_TRIGGER,
                    "cover": {
                        **NAMED_COVER_ACTIONS,
                        "state": "{{ true }}",
                        "availability": "{{ x - 12 }}",
                    },
                }
            },
            template.DOMAIN,
        ),
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, caplog_setup_text
) -> None:
    """Test that an invalid availability keeps the device available."""

    # This forces a trigger for trigger based entities
    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID) != STATE_UNAVAILABLE

    err = "UndefinedError: 'x' is undefined"
    assert err in caplog_setup_text or err in caplog.text


@pytest.mark.parametrize(
    ("count", "state_template", "attribute", "attribute_template"),
    [(1, "{{ 1 == 1 }}", "device_class", "door")],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_single_attribute_state_cover")
async def test_device_class(hass: HomeAssistant) -> None:
    """Test device class."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("device_class") == "door"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute", "attribute_template"),
    [(0, "{{ 1 == 1 }}", "device_class", "barnacle_bill")],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_single_attribute_state_cover")
async def test_invalid_device_class(hass: HomeAssistant) -> None:
    """Test device class."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert not state


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("cover_config", "style"),
    [
        (
            {
                "test_template_cover_01": UNIQUE_ID_CONFIG,
                "test_template_cover_02": UNIQUE_ID_CONFIG,
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            [
                {
                    "name": "test_template_cover_01",
                    **UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_cover_02",
                    **UNIQUE_ID_CONFIG,
                },
            ],
            ConfigurationStyle.MODERN,
        ),
        (
            [
                {
                    "name": "test_template_cover_01",
                    **UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_cover_02",
                    **UNIQUE_ID_CONFIG,
                },
            ],
            ConfigurationStyle.TRIGGER,
        ),
    ],
)
@pytest.mark.usefixtures("setup_cover")
async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id option only creates one cover per id."""
    assert len(hass.states.async_all()) == 1


async def test_nested_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a template unique_id propagates to switch unique_ids."""
    with assert_setup_component(1, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {
                "template": {
                    "unique_id": "x",
                    "cover": [
                        {
                            **COVER_ACTIONS,
                            "name": "test_a",
                            "unique_id": "a",
                            "state": "{{ true }}",
                        },
                        {
                            **COVER_ACTIONS,
                            "name": "test_b",
                            "unique_id": "b",
                            "state": "{{ true }}",
                        },
                    ],
                },
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all("cover")) == 2

    entry = entity_registry.async_get("cover.test_a")
    assert entry
    assert entry.unique_id == "x-a"

    entry = entity_registry.async_get("cover.test_b")
    assert entry
    assert entry.unique_id == "x-b"


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "cover_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "garage_door": {
                    **COVER_ACTIONS,
                    "friendly_name": "Garage Door",
                    "value_template": "{{ is_state('binary_sensor.garage_door_sensor', 'off') }}",
                },
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "name": "Garage Door",
                **COVER_ACTIONS,
                "state": "{{ is_state('binary_sensor.garage_door_sensor', 'off') }}",
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "name": "Garage Door",
                **COVER_ACTIONS,
                "state": "{{ is_state('binary_sensor.garage_door_sensor', 'off') }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_cover")
async def test_state_gets_lowercased(hass: HomeAssistant) -> None:
    """Test True/False is lowercased."""

    hass.states.async_set("binary_sensor.garage_door_sensor", "off")
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("cover.garage_door").state == CoverState.OPEN
    hass.states.async_set("binary_sensor.garage_door_sensor", "on")
    await hass.async_block_till_done()
    assert hass.states.get("cover.garage_door").state == CoverState.CLOSED


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states.cover.test_state.state }}",
            "mdi:window-shutter{{ '-open' if is_state('cover.test_template_cover', 'open') else '' }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "icon_template"),
        (ConfigurationStyle.MODERN, "icon"),
        (ConfigurationStyle.TRIGGER, "icon"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_cover")
async def test_self_referencing_icon_with_no_template_is_not_a_loop(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a self referencing icon with no value template is not a loop."""
    assert len(hass.states.async_all()) == 1

    assert "Template loop detected" not in caplog.text


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("script", "supported_feature"),
    [
        ("stop_cover", CoverEntityFeature.STOP),
        ("set_cover_position", CoverEntityFeature.SET_POSITION),
        (
            "set_cover_tilt_position",
            CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.STOP_TILT
            | CoverEntityFeature.SET_TILT_POSITION,
        ),
    ],
)
@pytest.mark.usefixtures("setup_empty_action")
async def test_empty_action_config(
    hass: HomeAssistant, supported_feature: CoverEntityFeature
) -> None:
    """Test configuration with empty script."""
    state = hass.states.get("cover.test_template_cover")
    assert (
        state.attributes["supported_features"]
        == CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | supported_feature
    )


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests creating a cover from a config entry."""

    hass.states.async_set(
        "cover.test_state",
        "open",
        {},
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "state": "{{ states('cover.test_state') }}",
            "set_cover_position": [],
            "template_type": COVER_DOMAIN,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("cover.my_template")
    assert state is not None
    assert state == snapshot


async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        cover.DOMAIN,
        {"name": "My template", "state": "{{ 'open' }}", "set_cover_position": []},
    )

    assert state["state"] == CoverState.OPEN
