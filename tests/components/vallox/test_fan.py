"""Tests for Vallox fan platform."""

from unittest.mock import AsyncMock, _Call, call, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from vallox_websocket_api import (
    MetricValue,
    Profile,
    ValloxApiException,
    ValloxInvalidInputException,
)

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    NotValidPresetModeError,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

FAN_ENTITY_ID = "fan.vallox"

HOME_PROFILE = {"A_CYC_STATE": 0}
AWAY_PROFILE = {"A_CYC_STATE": 1}
AUTO_PROFILE = {"A_CYC_STATE": 2}
UNKNOWN_PROFILE = {"A_CYC_STATE": 3}
BOOST_PROFILE = {"A_CYC_BOOST_TIMER": 30}
FIREPLACE_PROFILE = {"A_CYC_FIREPLACE_TIMER": 30}
EXTRA_PROFILE = {"A_CYC_EXTRA_TIMER": 30}


@pytest.mark.usefixtures("mock_vallox_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the fan entity."""
    with patch("homeassistant.components.vallox.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("metrics", "expected_state"),
    [
        pytest.param({"A_CYC_MODE": 0}, STATE_ON, id="on"),
        pytest.param({"A_CYC_MODE": 5}, STATE_OFF, id="off"),
    ],
)
async def test_fan_state(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    expected_state: str,
) -> None:
    """Test fan on/off state."""
    mock_vallox_client.fetch_metric_data.assert_called_once()
    state = hass.states.get(FAN_ENTITY_ID)
    assert state
    assert state.state == expected_state


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("metrics", "expected_preset", "expected_percentage"),
    [
        # The fan speeds come from metrics.json: Home 30, Away 10 and Boost 80.
        pytest.param(HOME_PROFILE, "Home", 30, id="home"),
        pytest.param(AWAY_PROFILE, "Away", 10, id="away"),
        pytest.param(BOOST_PROFILE, "Boost", 80, id="boost"),
        pytest.param(FIREPLACE_PROFILE, "Fireplace", None, id="fireplace"),
        pytest.param(EXTRA_PROFILE, "Extra", None, id="extra"),
        pytest.param(AUTO_PROFILE, "Auto", None, id="auto"),
        pytest.param(UNKNOWN_PROFILE, None, None, id="unknown"),
    ],
)
async def test_fan_profile(
    hass: HomeAssistant,
    expected_preset: str | None,
    expected_percentage: int | None,
) -> None:
    """Test the preset mode and fan speed of each profile."""
    state = hass.states.get(FAN_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == expected_preset
    assert state.attributes[ATTR_PERCENTAGE] == expected_percentage


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("metrics", [{"A_CYC_HOME_SPEED_SETTING": None}])
async def test_fan_speed_missing(hass: HomeAssistant) -> None:
    """Test a fan speed the unit does not report."""
    state = hass.states.get(FAN_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_PERCENTAGE] is None
    assert state.attributes["fan_speed_home"] is None


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "metrics", "expected_called_with"),
    [
        pytest.param(
            SERVICE_TURN_ON, {"A_CYC_MODE": 5}, {"A_CYC_MODE": 0}, id="turn_on"
        ),
        pytest.param(
            SERVICE_TURN_OFF, {"A_CYC_MODE": 0}, {"A_CYC_MODE": 5}, id="turn_off"
        ),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    service: str,
    expected_called_with: dict[str, MetricValue],
) -> None:
    """Test turn on/off."""
    await hass.services.async_call(
        FAN_DOMAIN, service, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True
    )

    mock_vallox_client.set_values.assert_called_once_with(expected_called_with)
    # One fetch at setup, and one refresh after the change.
    assert mock_vallox_client.fetch_metric_data.call_count == 2


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "metrics"),
    [
        pytest.param(SERVICE_TURN_ON, {"A_CYC_MODE": 0}, id="turn_on_when_on"),
        pytest.param(SERVICE_TURN_OFF, {"A_CYC_MODE": 5}, id="turn_off_when_off"),
    ],
)
async def test_turn_on_off_unchanged(
    hass: HomeAssistant, mock_vallox_client: AsyncMock, service: str
) -> None:
    """Test that turning the fan on or off when it already is does nothing."""
    await hass.services.async_call(
        FAN_DOMAIN, service, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True
    )

    mock_vallox_client.set_values.assert_not_called()
    mock_vallox_client.fetch_metric_data.assert_called_once()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "metrics"),
    [
        pytest.param(SERVICE_TURN_ON, {"A_CYC_MODE": 5}, id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, {"A_CYC_MODE": 0}, id="turn_off"),
    ],
)
async def test_turn_on_off_exception(
    hass: HomeAssistant, mock_vallox_client: AsyncMock, service: str
) -> None:
    """Test turn on/off when the unit returns an error."""
    mock_vallox_client.set_values.side_effect = ValloxApiException("Fake failure")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN, service, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True
        )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    (
        "metrics",
        "service_data",
        "expected_set_values_calls",
        "expected_set_profile_calls",
        "expected_set_fan_speed_calls",
    ),
    [
        pytest.param(
            {"A_CYC_MODE": 5},
            {ATTR_PERCENTAGE: 15, ATTR_PRESET_MODE: "Away"},
            [call({"A_CYC_MODE": 0})],
            [call(Profile.AWAY)],
            [call(Profile.AWAY, 15)],
            id="fan_off",
        ),
        pytest.param(
            {"A_CYC_MODE": 0},
            {ATTR_PERCENTAGE: 15, ATTR_PRESET_MODE: "Away"},
            [],
            [call(Profile.AWAY)],
            [call(Profile.AWAY, 15)],
            id="fan_on",
        ),
        pytest.param(
            {"A_CYC_MODE": 0},
            {ATTR_PRESET_MODE: "Away"},
            [],
            [call(Profile.AWAY)],
            [],
            id="preset_only",
        ),
        pytest.param(
            {"A_CYC_MODE": 0},
            {ATTR_PERCENTAGE: 40},
            [],
            [],
            [call(Profile.HOME, 40)],
            id="percentage_only",
        ),
    ],
)
async def test_turn_on_with_parameters(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    service_data: dict[str, int | str],
    expected_set_values_calls: list[_Call],
    expected_set_profile_calls: list[_Call],
    expected_set_fan_speed_calls: list[_Call],
) -> None:
    """Test turn on with a preset mode, a percentage, or both."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID} | service_data,
        blocking=True,
    )

    assert mock_vallox_client.set_values.call_args_list == expected_set_values_calls
    assert mock_vallox_client.set_profile.call_args_list == expected_set_profile_calls
    assert (
        mock_vallox_client.set_fan_speed.call_args_list == expected_set_fan_speed_calls
    )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("preset", "metrics", "expected_set_profile_calls", "expected_fetch_count"),
    [
        pytest.param("Home", AWAY_PROFILE, [call(Profile.HOME)], 2, id="home"),
        pytest.param("Away", HOME_PROFILE, [call(Profile.AWAY)], 2, id="away"),
        pytest.param("Boost", HOME_PROFILE, [call(Profile.BOOST)], 2, id="boost"),
        pytest.param(
            "Fireplace", HOME_PROFILE, [call(Profile.FIREPLACE)], 2, id="fireplace"
        ),
        pytest.param("Extra", HOME_PROFILE, [call(Profile.EXTRA)], 2, id="extra"),
        pytest.param("Auto", HOME_PROFILE, [call(Profile.AUTO)], 2, id="auto"),
        # Selecting the active preset changes nothing, so there is no refresh.
        pytest.param("Home", HOME_PROFILE, [], 1, id="no_change"),
    ],
)
async def test_set_preset_mode(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    preset: str,
    expected_set_profile_calls: list[_Call],
    expected_fetch_count: int,
) -> None:
    """Test set preset mode."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PRESET_MODE: preset},
        blocking=True,
    )

    assert mock_vallox_client.set_profile.call_args_list == expected_set_profile_calls
    assert mock_vallox_client.fetch_metric_data.call_count == expected_fetch_count


@pytest.mark.usefixtures("init_integration")
async def test_set_invalid_preset_mode(hass: HomeAssistant) -> None:
    """Test set an invalid preset mode."""
    with pytest.raises(NotValidPresetModeError) as exc:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PRESET_MODE: "Invalid"},
            blocking=True,
        )
    assert exc.value.translation_key == "not_valid_preset_mode"


@pytest.mark.usefixtures("init_integration")
async def test_set_preset_mode_exception(
    hass: HomeAssistant, mock_vallox_client: AsyncMock
) -> None:
    """Test set preset mode when the unit returns an error."""
    mock_vallox_client.set_profile.side_effect = ValloxApiException("Fake exception")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PRESET_MODE: "Away"},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    (
        "metrics",
        "percentage",
        "expected_set_fan_speed_calls",
        "expected_set_values_calls",
    ),
    [
        pytest.param(HOME_PROFILE, 40, [call(Profile.HOME, 40)], [], id="home"),
        pytest.param(AWAY_PROFILE, 30, [call(Profile.AWAY, 30)], [], id="away"),
        pytest.param(BOOST_PROFILE, 60, [call(Profile.BOOST, 60)], [], id="boost"),
        pytest.param(HOME_PROFILE, 0, [], [call({"A_CYC_MODE": 5})], id="turn_off"),
    ],
)
async def test_set_fan_speed(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    percentage: int,
    expected_set_fan_speed_calls: list[_Call],
    expected_set_values_calls: list[_Call],
) -> None:
    """Test set fan speed percentage."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PERCENTAGE: percentage},
        blocking=True,
    )

    assert (
        mock_vallox_client.set_fan_speed.call_args_list == expected_set_fan_speed_calls
    )
    assert mock_vallox_client.set_values.call_args_list == expected_set_values_calls


@pytest.mark.usefixtures("init_integration")
async def test_set_fan_speed_exception(
    hass: HomeAssistant, mock_vallox_client: AsyncMock
) -> None:
    """Test set fan speed percentage when the unit returns an error."""
    mock_vallox_client.set_fan_speed.side_effect = ValloxApiException("Fake failure")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PERCENTAGE: 5},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("metrics", [FIREPLACE_PROFILE])
async def test_set_fan_speed_unsupported_profile(
    hass: HomeAssistant, mock_vallox_client: AsyncMock
) -> None:
    """Test setting the fan speed in a profile that has no fan speed setting."""
    mock_vallox_client.set_fan_speed.side_effect = ValloxInvalidInputException(
        "Fan speed is not settable for profile"
    )

    with pytest.raises(ValueError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PERCENTAGE: 40},
            blocking=True,
        )

    mock_vallox_client.set_fan_speed.assert_called_once_with(Profile.FIREPLACE, 40)
