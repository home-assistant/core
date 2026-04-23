"""The tests for the Template cover platform."""

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
from homeassistant.helpers.typing import ConfigType

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    assert_action,
    async_get_flow_preview_state,
    async_trigger,
    make_test_action,
    make_test_trigger,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
)

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

TEST_STATE_ENTITY_ID = "sensor.test_state"
TEST_POSITION_ENTITY_ID = "sensor.test_position"
TEST_AVAILABILITY_ENTITY = "binary_sensor.availability"

TEST_COVER = TemplatePlatformSetup(
    cover.DOMAIN,
    "covers",
    "test_template_cover",
    make_test_trigger(
        TEST_STATE_ENTITY_ID,
        TEST_POSITION_ENTITY_ID,
        TEST_AVAILABILITY_ENTITY,
    ),
)

OPEN_COVER = make_test_action("open_cover")
CLOSE_COVER = make_test_action("close_cover")
STOP_COVER = make_test_action("stop_cover")
SET_COVER_POSITION = make_test_action(
    "set_cover_position", {"position": "{{ position }}"}
)
SET_COVER_TILT_POSITION = make_test_action(
    "set_cover_tilt_position", {"tilt_position": "{{ tilt }}"}
)

COVER_ACTIONS = {
    **OPEN_COVER,
    **CLOSE_COVER,
}


@pytest.fixture
async def setup_cover(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: ConfigType,
) -> None:
    """Do setup of cover integration."""
    await setup_entity(hass, TEST_COVER, style, count, config)


@pytest.fixture
async def setup_state_cover(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
    config: ConfigType,
):
    """Do setup of cover integration using a state template."""
    await setup_entity(hass, TEST_COVER, style, count, config, state_template)


@pytest.fixture
async def setup_position_cover(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    position_template: str,
    config: ConfigType,
):
    """Do setup of cover integration using a state template."""
    position_option = (
        "position_template" if style == ConfigurationStyle.LEGACY else "position"
    )
    await setup_entity(
        hass,
        TEST_COVER,
        style,
        count,
        config,
        extra_config={
            position_option: position_template,
            **SET_COVER_POSITION,
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
    await setup_entity(
        hass,
        TEST_COVER,
        style,
        count,
        {attribute: attribute_template} if attribute and attribute_template else {},
        state_template,
        COVER_ACTIONS,
    )


@pytest.fixture
async def setup_empty_action(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    script: str,
):
    """Do setup of cover integration using a empty actions template."""
    await setup_entity(
        hass,
        TEST_COVER,
        style,
        count,
        {"open_cover": [], "close_cover": [], script: []},
    )


@pytest.mark.parametrize(
    ("count", "state_template", "config"),
    [(1, "{{ states.sensor.test_state.state }}", COVER_ACTIONS)],
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
        ("dog", STATE_UNKNOWN, "Received invalid cover state: dog"),
        ("cat", STATE_UNKNOWN, "Received invalid cover state: cat"),
        ("bear", STATE_UNKNOWN, "Received invalid cover state: bear"),
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
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == STATE_UNKNOWN

    await async_trigger(hass, TEST_STATE_ENTITY_ID, set_state)

    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == test_state
    assert text in caplog.text


@pytest.mark.parametrize(("count", "config"), [(1, COVER_ACTIONS)])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("state_template", "expected"),
    [
        ("{{ 'open' }}", CoverState.OPEN),
        ("{{ 'on' }}", CoverState.OPEN),
        ("{{ 1 }}", CoverState.OPEN),
        ("{{ True }}", CoverState.OPEN),
        ("{{ 'closed' }}", CoverState.CLOSED),
        ("{{ 'off' }}", CoverState.CLOSED),
        ("{{ 0 }}", CoverState.CLOSED),
        ("{{ False }}", CoverState.CLOSED),
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

    await async_trigger(hass, TEST_STATE_ENTITY_ID, None)

    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == expected


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states('sensor.test_state') }}",
            "{{ states('sensor.test_position') }}",
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
@pytest.mark.usefixtures("setup_single_attribute_state_cover")
async def test_template_state_text_with_position(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the state of a position template in order."""
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == STATE_UNKNOWN

    # Test the open/closed states are ignored when state template updates.
    await async_trigger(hass, TEST_STATE_ENTITY_ID, CoverState.OPEN)
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == STATE_UNKNOWN

    await async_trigger(hass, TEST_STATE_ENTITY_ID, CoverState.CLOSED)
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == STATE_UNKNOWN

    # Test the opening/closing state are honored when state template updates.
    await async_trigger(hass, TEST_STATE_ENTITY_ID, CoverState.OPENING)
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == CoverState.OPENING

    await async_trigger(hass, TEST_STATE_ENTITY_ID, CoverState.CLOSING)
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == CoverState.CLOSING

    # Test the open/closed states are honored when position template updates.
    await async_trigger(hass, TEST_POSITION_ENTITY_ID, 0)
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == CoverState.CLOSING
    assert state.attributes.get("current_position") == 0

    # Test the closed state is ignored when position is already set.
    await async_trigger(hass, TEST_STATE_ENTITY_ID, CoverState.OPEN)
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == CoverState.CLOSED
    assert state.attributes.get("current_position") == 0

    # Test the open/closed states are honored when position template updates.
    await async_trigger(hass, TEST_POSITION_ENTITY_ID, 10)
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == CoverState.OPEN
    assert state.attributes.get("current_position") == 10

    assert "Received invalid cover state" not in caplog.text

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "dog")
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == CoverState.OPEN
    assert state.attributes.get("current_position") == 10
    assert "Received invalid cover state: dog" in caplog.text


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states.sensor.test_state.state }}",
            "{{ state_attr('sensor.test_state', 'position') }}",
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
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == STATE_UNKNOWN

    await async_trigger(hass, TEST_STATE_ENTITY_ID, set_state)

    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("count", "position_template", "config"),
    [(1, "{{ states('sensor.test_state') }}", COVER_ACTIONS)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("position", "expected"),
    [(42, CoverState.OPEN), (0.0, CoverState.CLOSED), (None, STATE_UNKNOWN)],
)
@pytest.mark.usefixtures("setup_position_cover")
async def test_template_position(
    hass: HomeAssistant,
    position: int | None,
    expected: str,
    caplog: pytest.LogCaptureFixture,
    calls: list[ServiceCall],
) -> None:
    """Test the position_template attribute."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, position)

    state = hass.states.get(TEST_COVER.entity_id)
    assert state.attributes.get("current_position") == position
    assert state.state == expected
    assert "ValueError" not in caplog.text

    # Test to make sure optimistic is not set with only a position template.
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: TEST_COVER.entity_id, "position": 10},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_COVER.entity_id)
    assert state.attributes.get("current_position") == position
    assert state.state == expected


@pytest.mark.parametrize(
    ("count", "config"), [(1, {**COVER_ACTIONS, "optimistic": False})]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_cover")
async def test_template_not_optimistic(
    hass: HomeAssistant,
    calls: list[ServiceCall],
) -> None:
    """Test the is_closed attribute."""
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == STATE_UNKNOWN

    # Test to make sure optimistic is not set with only a position template.
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: TEST_COVER.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == STATE_UNKNOWN

    # Test to make sure optimistic is not set with only a position template.
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: TEST_COVER.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_COVER.entity_id)
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
    await async_trigger(hass, TEST_STATE_ENTITY_ID, None)

    state = hass.states.get(TEST_COVER.entity_id)
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
    await async_trigger(hass, TEST_STATE_ENTITY_ID, None)

    state = hass.states.get(TEST_COVER.entity_id)
    assert state.attributes.get("current_position") is None


@pytest.mark.parametrize(("count", "state_template"), [(0, "{{ 1 == 1 }}")])
@pytest.mark.parametrize(
    ("style", "config", "error"),
    [
        (
            ConfigurationStyle.LEGACY,
            {},
            "Invalid config for 'cover' from integration 'template'",
        ),
        (
            ConfigurationStyle.LEGACY,
            OPEN_COVER,
            "Invalid config for 'cover' from integration 'template'",
        ),
        (
            ConfigurationStyle.MODERN,
            {},
            "Invalid config for 'template': must contain at least one of open_cover, set_cover_position.",
        ),
        (
            ConfigurationStyle.MODERN,
            OPEN_COVER,
            "Invalid config for 'template': some but not all values in the same group of inclusion 'open_or_close'",
        ),
        (
            ConfigurationStyle.TRIGGER,
            {},
            "Invalid config for 'template': must contain at least one of open_cover, set_cover_position.",
        ),
        (
            ConfigurationStyle.TRIGGER,
            OPEN_COVER,
            "Invalid config for 'template': some but not all values in the same group of inclusion 'open_or_close'",
        ),
    ],
)
@pytest.mark.usefixtures("setup_state_cover")
async def test_template_open_or_position(
    hass: HomeAssistant,
    error: str,
    caplog_setup_text: str,
) -> None:
    """Test that at least one of open_cover or set_position is used."""
    assert hass.states.async_all("cover") == []
    assert error in caplog_setup_text


@pytest.mark.parametrize(
    ("count", "position_template", "config"),
    [(1, "{{ 0 }}", COVER_ACTIONS)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_position_cover")
async def test_open_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test the open_cover command."""

    # This forces a trigger for trigger based entities
    await async_trigger(hass, TEST_STATE_ENTITY_ID, None)

    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == CoverState.CLOSED

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: TEST_COVER.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert_action(TEST_COVER, calls, 1, "open_cover")


@pytest.mark.parametrize(
    ("count", "state_template", "config"),
    [(1, "{{ 1==1 }}", {**COVER_ACTIONS, **STOP_COVER})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_cover")
async def test_close_stop_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test the close-cover and stop_cover commands."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, None)

    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == CoverState.OPEN

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: TEST_COVER.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: TEST_COVER.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert_action(TEST_COVER, calls, 2, "close_cover", index=0)
    assert_action(TEST_COVER, calls, 2, "stop_cover")


@pytest.mark.parametrize(("count", "config"), [(1, SET_COVER_POSITION)])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_cover")
async def test_set_position(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test the set_position command."""
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == STATE_UNKNOWN

    expected_calls = 1
    for service, position, options in (
        (SERVICE_OPEN_COVER, 100, {}),
        (SERVICE_CLOSE_COVER, 0, {}),
        (SERVICE_TOGGLE, 100, {}),
        (SERVICE_TOGGLE, 0, {}),
        (SERVICE_SET_COVER_POSITION, 25, {ATTR_POSITION: 25}),
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: TEST_COVER.entity_id, **options},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get(TEST_COVER.entity_id)
        assert state.attributes.get("current_position") == position
        assert_action(
            TEST_COVER, calls, expected_calls, "set_cover_position", position=position
        )
        expected_calls += 1


@pytest.mark.parametrize(
    ("count", "config"), [(1, {**COVER_ACTIONS, **SET_COVER_TILT_POSITION})]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("service", "options", "tilt_position"),
    [
        (
            SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_TILT_POSITION: 42},
            42,
        ),
        (SERVICE_OPEN_COVER_TILT, {}, 100),
        (SERVICE_CLOSE_COVER_TILT, {}, 0),
    ],
)
@pytest.mark.usefixtures("setup_cover")
async def test_set_tilt_position(
    hass: HomeAssistant,
    service,
    options,
    tilt_position,
    calls: list[ServiceCall],
) -> None:
    """Test the set_tilt_position command."""
    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: TEST_COVER.entity_id, **options},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert_action(
        TEST_COVER, calls, 1, "set_cover_tilt_position", tilt_position=tilt_position
    )


@pytest.mark.parametrize(("count", "config"), [(1, SET_COVER_POSITION)])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_cover")
async def test_set_position_optimistic(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test optimistic position mode."""
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.attributes.get("current_position") is None

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: TEST_COVER.entity_id, ATTR_POSITION: 42},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.attributes.get("current_position") == 42.0

    for service, test_state in (
        (SERVICE_CLOSE_COVER, CoverState.CLOSED),
        (SERVICE_OPEN_COVER, CoverState.OPEN),
        (SERVICE_TOGGLE, CoverState.CLOSED),
        (SERVICE_TOGGLE, CoverState.OPEN),
    ):
        await hass.services.async_call(
            COVER_DOMAIN, service, {ATTR_ENTITY_ID: TEST_COVER.entity_id}, blocking=True
        )
        await hass.async_block_till_done()
        state = hass.states.get(TEST_COVER.entity_id)
        assert state.state == test_state


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "config"),
    [
        (
            ConfigurationStyle.TRIGGER,
            {
                **SET_COVER_POSITION,
                "picture": "{{ 'foo.png' if is_state('sensor.test_state', 'open') else 'bar.png' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_cover")
async def test_non_optimistic_template_with_optimistic_state(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test optimistic state with non-optimistic template."""
    state = hass.states.get(TEST_COVER.entity_id)
    assert "entity_picture" not in state.attributes

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: TEST_COVER.entity_id, ATTR_POSITION: 42},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == CoverState.OPEN
    assert state.attributes["current_position"] == 42.0
    assert "entity_picture" not in state.attributes

    await async_trigger(hass, TEST_STATE_ENTITY_ID, CoverState.OPEN)

    state = hass.states.get(TEST_COVER.entity_id)
    assert state.state == CoverState.OPEN
    assert state.attributes["current_position"] == 42.0
    assert state.attributes["entity_picture"] == "foo.png"


@pytest.mark.parametrize(
    ("count", "position_template", "config"),
    [(1, "{{ 100 }}", SET_COVER_TILT_POSITION)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_position_cover")
async def test_set_tilt_position_optimistic(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test the optimistic tilt_position mode."""
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.attributes.get("current_tilt_position") is None

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: TEST_COVER.entity_id, ATTR_TILT_POSITION: 42},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.attributes.get("current_tilt_position") == 42.0

    for service, pos in (
        (SERVICE_CLOSE_COVER_TILT, 0.0),
        (SERVICE_OPEN_COVER_TILT, 100.0),
        (SERVICE_TOGGLE_COVER_TILT, 0.0),
        (SERVICE_TOGGLE_COVER_TILT, 100.0),
    ):
        await hass.services.async_call(
            COVER_DOMAIN, service, {ATTR_ENTITY_ID: TEST_COVER.entity_id}, blocking=True
        )
        await hass.async_block_till_done()
        state = hass.states.get(TEST_COVER.entity_id)
        assert state.attributes.get("current_tilt_position") == pos


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states.sensor.test_state.state }}",
            "{% if states.sensor.test_state.state %}mdi:check{% endif %}",
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
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.attributes.get("icon") == initial_expected_state

    await async_trigger(hass, TEST_STATE_ENTITY_ID, CoverState.OPEN)

    state = hass.states.get(TEST_COVER.entity_id)

    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states.sensor.test_state.state }}",
            "{% if states.sensor.test_state.state %}/local/cover.png{% endif %}",
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
    state = hass.states.get(TEST_COVER.entity_id)
    assert state.attributes.get("entity_picture") == initial_expected_state

    await async_trigger(hass, TEST_STATE_ENTITY_ID, CoverState.OPEN)

    state = hass.states.get(TEST_COVER.entity_id)

    assert state.attributes["entity_picture"] == "/local/cover.png"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{{ is_state('binary_sensor.availability','on') }}",
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
    await async_trigger(hass, TEST_AVAILABILITY_ENTITY, STATE_OFF)
    assert hass.states.get(TEST_COVER.entity_id).state == STATE_UNAVAILABLE

    await async_trigger(hass, TEST_AVAILABILITY_ENTITY, STATE_ON)
    assert hass.states.get(TEST_COVER.entity_id).state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [(1, "{{ true }}", "{{ x - 12 }}")],
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
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, caplog_setup_text
) -> None:
    """Test that an invalid availability keeps the device available."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    assert hass.states.get(TEST_COVER.entity_id) != STATE_UNAVAILABLE
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
    state = hass.states.get(TEST_COVER.entity_id)
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
    state = hass.states.get(TEST_COVER.entity_id)
    assert not state


@pytest.mark.parametrize("config", [COVER_ACTIONS])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_unique_id(
    hass: HomeAssistant, style: ConfigurationStyle, config: ConfigType
) -> None:
    """Test unique_id option only creates one cover per id."""
    await setup_and_test_unique_id(hass, TEST_COVER, style, config)


@pytest.mark.parametrize("config", [COVER_ACTIONS])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_nested_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a template unique_id propagates to cover unique_ids."""
    await setup_and_test_nested_unique_id(
        hass, TEST_COVER, style, entity_registry, config
    )


@pytest.mark.parametrize(
    ("count", "state_template", "config"),
    [(1, "{{ is_state('sensor.test_state', 'off') }}", COVER_ACTIONS)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_cover")
async def test_state_gets_lowercased(hass: HomeAssistant) -> None:
    """Test True/False is lowercased."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    assert len(hass.states.async_all()) == 2

    assert hass.states.get(TEST_COVER.entity_id).state == CoverState.OPEN

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    assert hass.states.get(TEST_COVER.entity_id).state == CoverState.CLOSED


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states.sensor.test_state.state }}",
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
        TEST_STATE_ENTITY_ID,
        "open",
        {},
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "state": "{{ states('sensor.test_state') }}",
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
