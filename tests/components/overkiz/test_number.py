"""Tests for the Overkiz number platform."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName, OverkizCommand, OverkizCommandParam, OverkizState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.overkiz.number import (
    _async_set_native_value_away_mode_duration,
    _overkiz_value_fn_away_mode_duration,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import assert_command_call, async_deliver_events, build_event

from tests.common import snapshot_platform

MEMORIZED_POSITION = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/12184029",
    "number.garden_house_shutter_my_position",
)
OFFICE_BLINDS_MEMORIZED_POSITION = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe.json",
    "io://1234-5678-6508/4877511",
    "number.office_blinds_my_position",
)
EXPECTED_NUMBER_OF_SHOWER = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "io://1234-5678-5643/109286#1",
    "number.patio_water_heating_expected_number_of_shower",
)
COMFORT_ROOM_TEMPERATURE = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "ovp://1234-5678-1698/374762#1",
    "number.terrace_radiator_comfort_room_temperature",
)

SNAPSHOT_FIXTURES = [
    MEMORIZED_POSITION,
    OFFICE_BLINDS_MEMORIZED_POSITION,
    EXPECTED_NUMBER_OF_SHOWER,
    COMFORT_ROOM_TEMPERATURE,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to number only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.NUMBER]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_number_set_value(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test setting a number value sends the correct command."""
    await setup_overkiz_integration(fixture=EXPECTED_NUMBER_OF_SHOWER.fixture)

    state = hass.states.get(EXPECTED_NUMBER_OF_SHOWER.entity_id)
    assert state
    assert state.state == "4"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: EXPECTED_NUMBER_OF_SHOWER.entity_id, ATTR_VALUE: 3},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=EXPECTED_NUMBER_OF_SHOWER.device_url,
        command_name="setExpectedNumberOfShower",
        parameters=[3],
    )


async def test_number_dynamic_min_max(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test that min/max values are read from device states when available."""
    await setup_overkiz_integration(fixture=EXPECTED_NUMBER_OF_SHOWER.fixture)

    state = hass.states.get(EXPECTED_NUMBER_OF_SHOWER.entity_id)
    assert state
    assert state.attributes["min"] == 2
    assert state.attributes["max"] == 4


async def test_number_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event-driven state update for a number entity."""
    await setup_overkiz_integration(fixture=EXPECTED_NUMBER_OF_SHOWER.fixture)

    state = hass.states.get(EXPECTED_NUMBER_OF_SHOWER.entity_id)
    assert state
    assert state.state == "4"

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=EXPECTED_NUMBER_OF_SHOWER.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_EXPECTED_NUMBER_OF_SHOWER.value,
                        "type": 1,
                        "value": 3,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(EXPECTED_NUMBER_OF_SHOWER.entity_id)
    assert state.state == "3"


async def test_number_unavailability(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test number becomes unavailable when device goes offline."""
    await setup_overkiz_integration(fixture=EXPECTED_NUMBER_OF_SHOWER.fixture)

    state = hass.states.get(EXPECTED_NUMBER_OF_SHOWER.entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_UNAVAILABLE.value,
                device_url=EXPECTED_NUMBER_OF_SHOWER.device_url,
            )
        ],
    )

    assert (
        hass.states.get(EXPECTED_NUMBER_OF_SHOWER.entity_id).state == STATE_UNAVAILABLE
    )


def _make_device(op_mode_value=None, duration_value=None) -> MagicMock:
    """Build a minimal mock Device with the relevant states."""
    device = MagicMock()

    def states_get(key):
        if key == OverkizState.CORE_OPERATING_MODE:
            if op_mode_value is None:
                return None
            state = MagicMock()
            state.value = op_mode_value
            return state
        if key == OverkizState.IO_AWAY_MODE_DURATION:
            if duration_value is None:
                return None
            state = MagicMock()
            state.value = duration_value
            return state
        return None

    device.states.get.side_effect = states_get
    return device


def test_value_fn_absence_off_returns_zero() -> None:
    """When core:OperatingModeState has absence=off, return 0 regardless of duration."""
    device = _make_device(
        op_mode_value={OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF},
        duration_value="52",
    )
    assert _overkiz_value_fn_away_mode_duration(device) == 0.0


def test_value_fn_absence_on_duration_always_returns_99() -> None:
    """When absence is on and duration is 'always', return 99."""
    device = _make_device(
        op_mode_value={OverkizCommandParam.ABSENCE: OverkizCommandParam.ON},
        duration_value=OverkizCommandParam.ALWAYS,
    )
    assert _overkiz_value_fn_away_mode_duration(device) == 99.0


def test_value_fn_absence_on_timed_duration() -> None:
    """When absence is on and duration is a number, return the float value."""
    device = MagicMock()

    def states_get(key):
        if key == OverkizState.CORE_OPERATING_MODE:
            state = MagicMock()
            state.value = {OverkizCommandParam.ABSENCE: OverkizCommandParam.ON}
            return state
        if key == OverkizState.IO_AWAY_MODE_DURATION:
            state = MagicMock()
            state.value = "52"
            return state
        return None

    device.states.get.side_effect = states_get
    assert _overkiz_value_fn_away_mode_duration(device) == 52.0


def test_value_fn_no_op_mode_state_duration_always() -> None:
    """When core:OperatingModeState is absent, fall back to duration state."""
    device = _make_device(op_mode_value=None, duration_value=OverkizCommandParam.ALWAYS)
    assert _overkiz_value_fn_away_mode_duration(device) == 99.0


def test_value_fn_no_op_mode_state_timed_duration() -> None:
    """When core:OperatingModeState is absent, return numeric duration."""
    device = _make_device(op_mode_value=None, duration_value="14")
    assert _overkiz_value_fn_away_mode_duration(device) == 14.0


def test_value_fn_no_duration_state_returns_none() -> None:
    """When io:AwayModeDurationState is absent, return None."""
    device = _make_device(
        op_mode_value={OverkizCommandParam.ABSENCE: OverkizCommandParam.ON},
        duration_value=None,
    )
    assert _overkiz_value_fn_away_mode_duration(device) is None


def test_value_fn_op_mode_not_dict_falls_through() -> None:
    """When core:OperatingModeState value is not a dict, fall through to duration."""
    device = _make_device(op_mode_value="unexpected_string", duration_value="7")
    assert _overkiz_value_fn_away_mode_duration(device) == 7.0


async def test_set_value_zero_cancels_absence() -> None:
    """Value 0 must cancel absence via SET_CURRENT_OPERATING_MODE(absence=off)."""
    execute = AsyncMock()
    with patch("homeassistant.components.overkiz.number.asyncio.sleep"):
        await _async_set_native_value_away_mode_duration(0, execute)

    execute.assert_any_call(
        OverkizCommand.SET_CURRENT_OPERATING_MODE,
        {
            OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
            OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
        },
    )
    execute.assert_called_with(OverkizCommand.REFRESH_AWAY_MODE_DURATION)


async def test_set_value_one_cancels_absence() -> None:
    """Value 1 is unsupported by the device and must cancel absence."""
    execute = AsyncMock()
    with patch("homeassistant.components.overkiz.number.asyncio.sleep"):
        await _async_set_native_value_away_mode_duration(1, execute)

    execute.assert_any_call(
        OverkizCommand.SET_CURRENT_OPERATING_MODE,
        {
            OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
            OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
        },
    )


async def test_set_value_timed_duration() -> None:
    """Values 2-98 must set duration then activate absence."""
    execute = AsyncMock()
    with patch("homeassistant.components.overkiz.number.asyncio.sleep"):
        await _async_set_native_value_away_mode_duration(52, execute)

    calls = execute.call_args_list
    assert calls[0] == call(OverkizCommand.SET_AWAY_MODE_DURATION, 52)
    assert calls[1] == call(
        OverkizCommand.SET_CURRENT_OPERATING_MODE,
        {
            OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
            OverkizCommandParam.ABSENCE: OverkizCommandParam.ON,
        },
    )
    assert calls[-1] == call(OverkizCommand.REFRESH_AWAY_MODE_DURATION)


async def test_set_value_99_indefinite_absence() -> None:
    """Value 99 must cancel first then activate without duration (device reports 'always')."""
    execute = AsyncMock()
    with patch("homeassistant.components.overkiz.number.asyncio.sleep"):
        await _async_set_native_value_away_mode_duration(99, execute)

    calls = execute.call_args_list
    assert calls[0] == call(
        OverkizCommand.SET_CURRENT_OPERATING_MODE,
        {
            OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
            OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
        },
    )
    assert calls[1] == call(
        OverkizCommand.SET_CURRENT_OPERATING_MODE,
        {
            OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
            OverkizCommandParam.ABSENCE: OverkizCommandParam.ON,
        },
    )
    assert calls[-1] == call(OverkizCommand.REFRESH_AWAY_MODE_DURATION)
