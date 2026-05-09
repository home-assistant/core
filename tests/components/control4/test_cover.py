"""Test Control4 Cover."""

from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.control4.const import DEFAULT_SCAN_INTERVAL
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    CoverState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "cover.test_controller_living_room_shade"


def _make_cover_data(
    level: int | None = 50,
    fully_closed: bool = False,
    fully_open: bool = False,
    opening: bool = False,
    closing: bool = False,
) -> dict[int, dict[str, Any]]:
    """Build mock cover variable data for item ID 234."""
    return {
        234: {
            "Level": level,
            "Fully Closed": fully_closed,
            "Fully Open": fully_open,
            "Opening": opening,
            "Closing": closing,
        }
    }


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms which should be loaded during the test."""
    return [Platform.COVER]


@pytest.fixture
def mock_cover_variables() -> dict:
    """Mock cover variable data for default blind state."""
    return _make_cover_data()


@pytest.fixture
def mock_cover_update_variables(
    mock_cover_variables: dict,
) -> Generator[AsyncMock]:
    """Mock update_variables for cover platform."""

    async def _mock_update_variables(*args, **kwargs):
        return mock_cover_variables

    with patch(
        "homeassistant.components.control4.cover.update_variables_for_config_entry",
        new=_mock_update_variables,
    ) as mock_update:
        yield mock_update


@pytest.fixture
def mock_c4_blind() -> Generator[MagicMock]:
    """Mock C4Blind class."""
    with patch(
        "homeassistant.components.control4.cover.C4Blind", autospec=True
    ) as mock_class:
        mock_instance = mock_class.return_value
        mock_instance.open = AsyncMock()
        mock_instance.close = AsyncMock()
        mock_instance.stop = AsyncMock()
        mock_instance.setLevelTarget = AsyncMock()
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
    "mock_cover_update_variables",
    "init_integration",
)
async def test_cover_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cover entities are set up correctly with proper attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("mock_cover_variables", "expected_state", "expected_position"),
    [
        pytest.param(
            _make_cover_data(level=0, fully_closed=True),
            CoverState.CLOSED,
            0,
            id="closed",
        ),
        pytest.param(
            _make_cover_data(level=100, fully_open=True),
            CoverState.OPEN,
            100,
            id="open",
        ),
        pytest.param(
            _make_cover_data(level=42),
            CoverState.OPEN,
            42,
            id="partial",
        ),
        pytest.param(
            _make_cover_data(level=70, opening=True),
            CoverState.OPENING,
            70,
            id="opening",
        ),
        pytest.param(
            _make_cover_data(level=30, closing=True),
            CoverState.CLOSING,
            30,
            id="closing",
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_cover_update_variables",
    "init_integration",
)
async def test_cover_states(
    hass: HomeAssistant,
    expected_state: str,
    expected_position: int,
) -> None:
    """Test cover entity reports the correct state across positions."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes[ATTR_CURRENT_POSITION] == expected_position


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_cover_update_variables",
    "init_integration",
)
async def test_open_cover(
    hass: HomeAssistant,
    mock_c4_blind: MagicMock,
) -> None:
    """Test opening the cover dispatches to pyControl4."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_c4_blind.open.assert_called_once_with()


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_cover_update_variables",
    "init_integration",
)
async def test_close_cover(
    hass: HomeAssistant,
    mock_c4_blind: MagicMock,
) -> None:
    """Test closing the cover dispatches to pyControl4."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_c4_blind.close.assert_called_once_with()


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_cover_update_variables",
    "init_integration",
)
async def test_stop_cover(
    hass: HomeAssistant,
    mock_c4_blind: MagicMock,
) -> None:
    """Test stopping the cover dispatches to pyControl4."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_c4_blind.stop.assert_called_once_with()


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_cover_update_variables",
    "init_integration",
)
async def test_set_cover_position(
    hass: HomeAssistant,
    mock_c4_blind: MagicMock,
) -> None:
    """Test setting cover position calls setLevelTarget with the requested value."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 75},
        blocking=True,
    )
    mock_c4_blind.setLevelTarget.assert_called_once_with(75)


@pytest.mark.parametrize("mock_cover_variables", [{}])
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_cover_update_variables",
    "init_integration",
)
async def test_cover_not_created_when_no_initial_data(
    hass: HomeAssistant,
) -> None:
    """Test cover entity is not created when coordinator has no initial data."""
    state = hass.states.get(ENTITY_ID)
    assert state is None


@pytest.mark.parametrize(
    ("mock_cover_variables", "expected_position", "expected_state"),
    [
        pytest.param(
            {234: {}},
            None,
            STATE_UNKNOWN,
            id="all_missing",
        ),
        pytest.param(
            {234: {"Level": 0}},
            0,
            CoverState.CLOSED,
            id="level_only_closed",
        ),
        pytest.param(
            {234: {"Level": 80}},
            80,
            CoverState.OPEN,
            id="level_only_open",
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_cover_update_variables",
    "init_integration",
)
async def test_cover_partial_variables(
    hass: HomeAssistant,
    expected_position: int | None,
    expected_state: str,
) -> None:
    """Cover handles missing variables — falls back to position-derived is_closed."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_CURRENT_POSITION) == expected_position
    assert state.state == expected_state


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director",
    "mock_cover_update_variables",
    "init_integration",
)
async def test_cover_unavailable_when_data_disappears(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cover_variables: dict,
) -> None:
    """Cover becomes unavailable if coordinator stops returning its idx."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_cover_variables.clear()
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
