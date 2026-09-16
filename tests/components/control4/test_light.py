"""Test Control4 Light."""

from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.control4.const import WEBSOCKET_RESYNC_INTERVAL_SEC
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.color import brightness_to_value, value_to_brightness

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

CONTROL4_BRIGHTNESS_SCALE = (1, 100)

DIMMER_ENTITY_ID = "light.test_controller_living_room_light"
SWITCH_ENTITY_ID = "light.test_controller_kitchen_switch"


def _make_light_data(
    dimmer_attrs: dict[str, Any] | None = None,
    switch_attrs: dict[str, Any] | None = None,
) -> dict[int, dict[str, Any]]:
    """Build mock light variable data for the dimmer (345) and switch (346)."""
    return {
        345: {"LIGHT_LEVEL": 50} if dimmer_attrs is None else dimmer_attrs,
        346: {"LIGHT_STATE": 1} if switch_attrs is None else switch_attrs,
    }


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms which should be loaded during the test."""
    return [Platform.LIGHT]


@pytest.fixture
def mock_light_variables() -> dict:
    """Mock light variable data for the default dimmer/switch state."""
    return _make_light_data()


@pytest.fixture
def mock_light_update_variables(
    mock_light_variables: dict,
    mock_c4_director: MagicMock,
) -> None:
    """Mock the Director API so tests exercise the real Undefined/empty-dict normalization."""

    async def _mock_get_item_variables(item_id: int) -> list[dict[str, Any]]:
        item_data = mock_light_variables.get(item_id, {})
        return [{"varName": name, "value": value} for name, value in item_data.items()]

    mock_c4_director.get_item_variables = AsyncMock(
        side_effect=_mock_get_item_variables
    )


@pytest.fixture
def mock_c4_light() -> Generator[MagicMock]:
    """Mock C4Light class."""
    with patch(
        "homeassistant.components.control4.light.C4Light", autospec=True
    ) as mock_class:
        mock_instance = mock_class.return_value
        mock_instance.ramp_to_level = AsyncMock()
        mock_instance.set_level = AsyncMock()
        yield mock_instance


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Control4 integration for testing."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_light_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light entities are set up correctly with proper attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("mock_light_variables", "expected_dimmer_on", "expected_brightness"),
    [
        pytest.param(
            _make_light_data(dimmer_attrs={"LIGHT_LEVEL": 0}),
            False,
            None,
            id="dimmer_off",
        ),
        pytest.param(
            _make_light_data(dimmer_attrs={"LIGHT_LEVEL": 100}),
            True,
            255,
            id="dimmer_full",
        ),
        pytest.param(
            _make_light_data(dimmer_attrs={"LIGHT_LEVEL": 50}),
            True,
            128,
            id="dimmer_partial",
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_dimmer_states(
    hass: HomeAssistant,
    expected_dimmer_on: bool,
    expected_brightness: int | None,
) -> None:
    """Test dimmer entity reports the correct on/off state and brightness."""
    state = hass.states.get(DIMMER_ENTITY_ID)
    assert state is not None
    assert (state.state == "on") is expected_dimmer_on
    assert state.attributes.get("brightness") == expected_brightness


@pytest.mark.parametrize(
    ("mock_light_variables", "expected_switch_on"),
    [
        pytest.param(
            _make_light_data(switch_attrs={"LIGHT_STATE": 0}), False, id="switch_off"
        ),
        pytest.param(
            _make_light_data(switch_attrs={"LIGHT_STATE": 1}), True, id="switch_on"
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_switch_states(
    hass: HomeAssistant,
    expected_switch_on: bool,
) -> None:
    """Test on/off-only light entity reports the correct state and no brightness."""
    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert (state.state == "on") is expected_switch_on
    assert state.attributes.get("brightness") is None


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_turn_on_dimmer_with_brightness_and_transition(
    hass: HomeAssistant,
    mock_c4_light: MagicMock,
) -> None:
    """Turning on a dimmer with brightness/transition ramps to the right level."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: DIMMER_ENTITY_ID, ATTR_BRIGHTNESS: 128, ATTR_TRANSITION: 2},
        blocking=True,
    )
    expected_level = round(brightness_to_value(CONTROL4_BRIGHTNESS_SCALE, 128))
    mock_c4_light.ramp_to_level.assert_called_once_with(expected_level, 2000)


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_turn_on_dimmer_without_brightness_defaults_to_full(
    hass: HomeAssistant,
    mock_c4_light: MagicMock,
) -> None:
    """Turning on a dimmer with no brightness given ramps to full, no transition."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: DIMMER_ENTITY_ID},
        blocking=True,
    )
    mock_c4_light.ramp_to_level.assert_called_once_with(100, 0)


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_turn_off_dimmer(
    hass: HomeAssistant,
    mock_c4_light: MagicMock,
) -> None:
    """Turning off a dimmer ramps to 0."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: DIMMER_ENTITY_ID},
        blocking=True,
    )
    mock_c4_light.ramp_to_level.assert_called_once_with(0, 0)


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_turn_on_switch(
    hass: HomeAssistant,
    mock_c4_light: MagicMock,
) -> None:
    """Turning on an on/off-only light calls set_level(100), not ramp_to_level."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    mock_c4_light.set_level.assert_called_once_with(100)
    mock_c4_light.ramp_to_level.assert_not_called()


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_turn_off_switch(
    hass: HomeAssistant,
    mock_c4_light: MagicMock,
) -> None:
    """Turning off an on/off-only light calls set_level(0), not ramp_to_level."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    mock_c4_light.set_level.assert_called_once_with(0)
    mock_c4_light.ramp_to_level.assert_not_called()


@pytest.mark.parametrize(
    "mock_light_variables",
    [
        pytest.param({}, id="item_ids_missing_from_response"),
        pytest.param({345: {}, 346: {}}, id="item_ids_present_with_no_variables"),
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_light_not_created_when_no_initial_data(hass: HomeAssistant) -> None:
    """Test light entities are not created when there is no initial variable data."""
    assert hass.states.get(DIMMER_ENTITY_ID) is None
    assert hass.states.get(SWITCH_ENTITY_ID) is None


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_light_unavailable_on_websocket_disconnect(
    hass: HomeAssistant,
    mock_c4_websocket: MagicMock,
) -> None:
    """Light becomes unavailable when the WebSocket disconnect callback fires."""
    state = hass.states.get(DIMMER_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    await mock_c4_websocket.disconnect_callback()
    await hass.async_block_till_done()

    state = hass.states.get(DIMMER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_light_push_update(
    hass: HomeAssistant,
    mock_c4_websocket: MagicMock,
) -> None:
    """Light state updates when a normal OnDataToUI push event arrives."""
    state = hass.states.get(DIMMER_ENTITY_ID)
    assert state is not None
    assert state.attributes["brightness"] == 128

    callback = mock_c4_websocket.item_callbacks[345][0]
    await callback(345, {"evtName": "OnDataToUI", "data": {"LIGHT_LEVEL": 100}})
    await hass.async_block_till_done()

    state = hass.states.get(DIMMER_ENTITY_ID)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == 255


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_light_is_on_falls_through_undefined_key(
    hass: HomeAssistant,
    mock_c4_websocket: MagicMock,
) -> None:
    """is_on checks later keys when an earlier one is present but Undefined."""
    callback = mock_c4_websocket.item_callbacks[345][0]
    await callback(
        345,
        {
            "evtName": "OnDataToUI",
            "data": {"LIGHT_LEVEL": "Undefined", "CURRENT_POWER": 80},
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(DIMMER_ENTITY_ID)
    assert state is not None
    assert state.state == "on"


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_light_reconnect_resyncs_state(
    hass: HomeAssistant,
    mock_c4_websocket: MagicMock,
    mock_light_variables: dict,
) -> None:
    """Light re-fetches and resyncs state after a WebSocket reconnect."""
    await mock_c4_websocket.disconnect_callback()
    await hass.async_block_till_done()

    state = hass.states.get(DIMMER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_light_variables[345]["LIGHT_LEVEL"] = 10

    await mock_c4_websocket.connect_callback()
    await hass.async_block_till_done()

    state = hass.states.get(DIMMER_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes["brightness"] == value_to_brightness(
        CONTROL4_BRIGHTNESS_SCALE, 10
    )


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_light_update_variables",
    "init_integration",
)
async def test_light_periodic_resync(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_light_variables: dict,
) -> None:
    """Light re-fetches and resyncs state on the periodic safety-net poll."""
    state = hass.states.get(DIMMER_ENTITY_ID)
    assert state is not None
    assert state.attributes["brightness"] == 128

    mock_light_variables[345]["LIGHT_LEVEL"] = 0

    freezer.tick(timedelta(seconds=WEBSOCKET_RESYNC_INTERVAL_SEC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(DIMMER_ENTITY_ID)
    assert state is not None
    assert state.state == "off"
