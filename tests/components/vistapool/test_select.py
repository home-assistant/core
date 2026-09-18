"""Tests for the Vistapool select platform."""

from collections.abc import Generator
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, patch

from aioaquarite import AquariteError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_STATE_CHANGED,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_capture_events, snapshot_platform


@pytest.fixture(autouse=True)
def _only_select_platform() -> Generator[None]:
    """Restrict integration setup to the select platform for these tests."""
    with patch("homeassistant.components.vistapool.PLATFORMS", [Platform.SELECT]):
        yield


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test select entities for the default fixture."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("raw_value", "expected_option"),
    [
        pytest.param(0, "manual", id="index_0"),
        pytest.param(2, "heat", id="index_2"),
        pytest.param(4, "intel", id="index_4"),
        pytest.param("3", "smart", id="string_index"),
    ],
)
async def test_select_current_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    raw_value: int | str,
    expected_option: str,
) -> None:
    """Test current_option maps the API integer (or stringified int) onto the option name."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"version": 1},
        "filtration": {"mode": raw_value},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("select.my_pool_pump_mode").state == expected_option


@pytest.mark.parametrize(
    "raw_value",
    [
        pytest.param(None, id="null"),
        pytest.param("garbage", id="non_numeric"),
        pytest.param(99, id="out_of_range"),
    ],
)
async def test_select_current_option_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    raw_value: Any,
) -> None:
    """Test current_option reports unknown for missing / unparsable / out-of-range raw values."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"version": 1},
        "filtration": {"mode": raw_value},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("select.my_pool_pump_mode").state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("entity_id", "option", "expected_path", "expected_index"),
    [
        pytest.param(
            "select.my_pool_pump_mode",
            "heat",
            "filtration.mode",
            2,
            id="pump_mode_heat",
        ),
        pytest.param(
            "select.my_pool_pump_speed",
            "medium",
            "filtration.manVel",
            1,
            id="pump_speed_medium",
        ),
        pytest.param(
            "select.my_pool_filtration_timer_speed_2",
            "high",
            "filtration.timerVel2",
            2,
            id="timer_2_high",
        ),
    ],
)
async def test_select_option_writes_index(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
    entity_id: str,
    option: str,
    expected_path: str,
    expected_index: int,
) -> None:
    """Test select_option writes the option's index to the right API path."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    mock_vistapool_client.set_value.assert_awaited_once_with(
        "ABCDEF1234567890", expected_path, expected_index
    )


@pytest.mark.parametrize(
    ("raw_value", "expected_option"),
    [
        pytest.param(0, "slow", id="slow"),
        pytest.param(1, "medium", id="medium"),
        pytest.param(2, "high", id="high"),
    ],
)
async def test_filtration_timer_speed_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    raw_value: int,
    expected_option: str,
) -> None:
    """Test every timer speed maps onto its option.

    The timer speeds are three-state like the manual pump speed, so high
    has to survive the library's value coercion; slow and medium would
    still map correctly even if the value were read as a boolean.
    """
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"version": 1},
        "filtration": {"timerVel1": raw_value},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get("select.my_pool_filtration_timer_speed_1").state
        == expected_option
    )


async def test_select_option_raises_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test select_option re-raises as HomeAssistantError when the library fails."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_vistapool_client.set_value.side_effect = AquariteError("boom")
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.my_pool_pump_mode", ATTR_OPTION: "heat"},
            blocking=True,
        )
    assert excinfo.value.translation_key == "set_failed"


_LIGHT_SCHEDULE_DATA = {
    "main": {"version": 1},
    "light": {"mode": 1, "status": 0, "freq": 86400, "from": 79200, "to": 3600},
}


async def test_light_selects_not_created_without_scheduling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test controllers without light scheduling do not get the light selects."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("select.my_pool_light_mode") is None
    assert hass.states.get("select.my_pool_light_schedule_frequency") is None


@pytest.mark.parametrize(
    ("mode", "status", "expected"),
    [
        pytest.param(1, 0, "auto", id="schedule_armed"),
        pytest.param(1, 1, "auto", id="schedule_armed_while_on"),
        pytest.param(0, 1, "on", id="manual_on"),
        pytest.param(0, 0, "off", id="manual_off"),
    ],
)
async def test_light_mode_current_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mode: int,
    status: int,
    expected: str,
) -> None:
    """Test the armed schedule wins over the on/off state."""
    data = deepcopy(_LIGHT_SCHEDULE_DATA)
    data["light"]["mode"] = mode
    data["light"]["status"] = status
    mock_vistapool_client.fetch_pool_data.return_value = data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("select.my_pool_light_mode").state == expected


@pytest.mark.parametrize(
    ("option", "expected_updates"),
    [
        pytest.param("off", {"light.mode": 0, "light.status": 0}, id="off"),
        pytest.param("on", {"light.mode": 0, "light.status": 1}, id="on"),
        pytest.param("auto", {"light.mode": 1}, id="auto"),
    ],
)
async def test_light_mode_select_writes_one_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    option: str,
    expected_updates: dict[str, int],
) -> None:
    """Test each option lands as a single multi-field command.

    Writing the fields separately would leave the controller half-applied
    between the two commands.
    """
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LIGHT_SCHEDULE_DATA)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.my_pool_light_mode", ATTR_OPTION: option},
        blocking=True,
    )

    mock_vistapool_client.set_values.assert_awaited_once_with(
        "ABCDEF1234567890", expected_updates
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param(86400, "daily", id="daily"),
        pytest.param(604800, "weekly", id="weekly"),
        pytest.param(12345, None, id="unknown_value"),
    ],
)
async def test_light_schedule_frequency_maps_raw_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    raw: int,
    expected: str | None,
) -> None:
    """Test the frequency maps by raw seconds, not by option index."""
    data = deepcopy(_LIGHT_SCHEDULE_DATA)
    data["light"]["freq"] = raw
    mock_vistapool_client.fetch_pool_data.return_value = data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.my_pool_light_schedule_frequency").state
    assert state == (expected or STATE_UNKNOWN)


async def test_light_schedule_frequency_writes_raw_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test selecting a frequency writes its raw seconds value."""
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LIGHT_SCHEDULE_DATA)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.my_pool_light_schedule_frequency",
            ATTR_OPTION: "weekly",
        },
        blocking=True,
    )

    mock_vistapool_client.set_value.assert_awaited_once_with(
        "ABCDEF1234567890", "light.freq", 604800
    )


async def test_select_reflects_choice_before_push(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test a select shows the chosen option without waiting for the push."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.my_pool_pump_speed", ATTR_OPTION: "high"},
        blocking=True,
    )

    assert hass.states.get("select.my_pool_pump_speed").state == "high"


async def test_light_mode_reflects_choice_before_push(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the light mode select applies every field of the chosen option."""
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LIGHT_SCHEDULE_DATA)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("select.my_pool_light_mode").state == "auto"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.my_pool_light_mode", ATTR_OPTION: "on"},
        blocking=True,
    )

    # Reads back as on only if both light.mode and light.status were applied.
    assert hass.states.get("select.my_pool_light_mode").state == "on"


async def test_light_schedule_frequency_reflects_choice_before_push(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the frequency select shows the chosen option immediately."""
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LIGHT_SCHEDULE_DATA)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.my_pool_light_schedule_frequency",
            ATTR_OPTION: "weekly",
        },
        blocking=True,
    )

    assert hass.states.get("select.my_pool_light_schedule_frequency").state == "weekly"


async def test_light_mode_never_publishes_partial_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test leaving auto does not briefly read as another option.

    light.mode and light.status both feed current_option, so applying them
    one at a time would publish an off state between the two writes.
    """
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LIGHT_SCHEDULE_DATA)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.my_pool_light_mode", ATTR_OPTION: "on"},
        blocking=True,
    )
    await hass.async_block_till_done()

    states = [
        event.data["new_state"].state
        for event in events
        if event.data["entity_id"] == "select.my_pool_light_mode"
    ]
    assert states == ["on"]


async def test_light_mode_raises_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a failed multi-field write raises and leaves the state alone."""
    mock_vistapool_client.fetch_pool_data.return_value = deepcopy(_LIGHT_SCHEDULE_DATA)
    mock_vistapool_client.set_values.side_effect = AquariteError("boom")
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("select.my_pool_light_mode").state == "auto"

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.my_pool_light_mode", ATTR_OPTION: "on"},
            blocking=True,
        )
    assert excinfo.value.translation_key == "set_failed"

    # The write never reached the controller, so nothing may be applied.
    assert hass.states.get("select.my_pool_light_mode").state == "auto"


async def test_light_schedule_frequency_created_for_zero_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a reported zero still creates the entity.

    Zero is a value the controller reports, not a missing field, so it must
    surface as an unknown option rather than silently dropping the entity.
    """
    data = deepcopy(_LIGHT_SCHEDULE_DATA)
    data["light"]["freq"] = 0
    mock_vistapool_client.fetch_pool_data.return_value = data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.my_pool_light_schedule_frequency")
    assert state is not None
    assert state.state == STATE_UNKNOWN
