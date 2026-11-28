"""Tests for the Vallox services."""

from typing import Any
from unittest.mock import AsyncMock

import probatio
import pytest
from vallox_websocket_api import Profile, ValloxApiException

from homeassistant.components.vallox.const import DOMAIN, PROFILE_DURATION_INDEFINITE
from homeassistant.components.vallox.services import (
    ValloxService,
    ValloxServiceArgument,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

FAN_ENTITY_ID = "fan.vallox"


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "profile"),
    [
        pytest.param(ValloxService.SET_PROFILE_FAN_SPEED_HOME, Profile.HOME, id="home"),
        pytest.param(ValloxService.SET_PROFILE_FAN_SPEED_AWAY, Profile.AWAY, id="away"),
        pytest.param(
            ValloxService.SET_PROFILE_FAN_SPEED_BOOST, Profile.BOOST, id="boost"
        ),
    ],
)
async def test_set_profile_fan_speed(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    service: ValloxService,
    profile: Profile,
) -> None:
    """Test the services for setting the fan speed of a profile."""
    await hass.services.async_call(
        DOMAIN, service, {ValloxServiceArgument.FAN_SPEED: 30}, blocking=True
    )

    mock_vallox_client.set_fan_speed.assert_called_once_with(profile, 30)
    # One fetch at setup, and one refresh after the change.
    assert mock_vallox_client.fetch_metric_data.call_count == 2


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("fan_speed", "expected_fan_speed"),
    [
        pytest.param(150, 100, id="above_maximum"),
        pytest.param(-5, 0, id="below_minimum"),
    ],
)
async def test_set_profile_fan_speed_clamped(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    fan_speed: int,
    expected_fan_speed: int,
) -> None:
    """Test that a fan speed out of range is clamped, not rejected."""
    await hass.services.async_call(
        DOMAIN,
        ValloxService.SET_PROFILE_FAN_SPEED_HOME,
        {ValloxServiceArgument.FAN_SPEED: fan_speed},
        blocking=True,
    )

    mock_vallox_client.set_fan_speed.assert_called_once_with(
        Profile.HOME, expected_fan_speed
    )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("profile_key", "profile"),
    [
        pytest.param("home", Profile.HOME, id="home"),
        pytest.param("away", Profile.AWAY, id="away"),
        pytest.param("boost", Profile.BOOST, id="boost"),
        pytest.param("fireplace", Profile.FIREPLACE, id="fireplace"),
        pytest.param("extra", Profile.EXTRA, id="extra"),
        pytest.param("auto", Profile.AUTO, id="auto"),
    ],
)
@pytest.mark.parametrize(
    ("duration_data", "duration"),
    [
        pytest.param({}, None, id="no_duration"),
        pytest.param({ValloxServiceArgument.DURATION: 15}, 15, id="15_minutes"),
    ],
)
async def test_set_profile(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    profile_key: str,
    profile: Profile,
    duration_data: dict[str, int],
    duration: int | None,
) -> None:
    """Test the service for activating a profile."""
    await hass.services.async_call(
        DOMAIN,
        ValloxService.SET_PROFILE,
        {ValloxServiceArgument.PROFILE: profile_key} | duration_data,
        blocking=True,
    )

    mock_vallox_client.set_profile.assert_called_once_with(profile, duration)
    # One fetch at setup, and one refresh after the change.
    assert mock_vallox_client.fetch_metric_data.call_count == 2


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("duration", "expected_duration"),
    [
        # The maximum is PROFILE_DURATION_INDEFINITE, so a longer duration
        # activates the profile without a timeout.
        pytest.param(70000, PROFILE_DURATION_INDEFINITE, id="above_maximum"),
        pytest.param(0, 1, id="below_minimum"),
    ],
)
async def test_set_profile_duration_clamped(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    duration: int,
    expected_duration: int,
) -> None:
    """Test that a duration out of range is clamped, not rejected."""
    await hass.services.async_call(
        DOMAIN,
        ValloxService.SET_PROFILE,
        {
            ValloxServiceArgument.PROFILE: "boost",
            ValloxServiceArgument.DURATION: duration,
        },
        blocking=True,
    )

    mock_vallox_client.set_profile.assert_called_once_with(
        Profile.BOOST, expected_duration
    )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "expected_profile"),
    [
        pytest.param(ValloxService.SET_PROFILE_FAN_SPEED_HOME, "home", id="home"),
        pytest.param(ValloxService.SET_PROFILE_FAN_SPEED_AWAY, "away", id="away"),
        pytest.param(ValloxService.SET_PROFILE_FAN_SPEED_BOOST, "boost", id="boost"),
    ],
)
async def test_set_profile_fan_speed_error(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    service: ValloxService,
    expected_profile: str,
) -> None:
    """Test error handling when setting the fan speed fails."""
    mock_vallox_client.set_fan_speed.side_effect = ValloxApiException(
        "Connection error"
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN, service, {ValloxServiceArgument.FAN_SPEED: 30}, blocking=True
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "failed_to_set_fan_speed_for_profile"
    assert exc_info.value.translation_placeholders == {
        "profile": expected_profile,
        "fan_speed": "30",
    }
    # Nothing changed, so there is no refresh after the fetch at setup.
    mock_vallox_client.fetch_metric_data.assert_called_once()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service_data", "translation_key", "translation_placeholders"),
    [
        pytest.param(
            {ValloxServiceArgument.PROFILE: "home"},
            "failed_to_set_profile",
            {"profile": "home"},
            id="home",
        ),
        pytest.param(
            {
                ValloxServiceArgument.PROFILE: "home",
                ValloxServiceArgument.DURATION: PROFILE_DURATION_INDEFINITE,
            },
            "failed_to_set_profile",
            {"profile": "home"},
            id="home_indefinite",
        ),
        pytest.param(
            {ValloxServiceArgument.PROFILE: "boost"},
            "failed_to_set_profile",
            {"profile": "boost"},
            id="boost",
        ),
        pytest.param(
            {
                ValloxServiceArgument.PROFILE: "boost",
                ValloxServiceArgument.DURATION: PROFILE_DURATION_INDEFINITE,
            },
            "failed_to_set_profile",
            {"profile": "boost"},
            id="boost_indefinite",
        ),
        pytest.param(
            {ValloxServiceArgument.PROFILE: "extra"},
            "failed_to_set_profile",
            {"profile": "extra"},
            id="extra",
        ),
        pytest.param(
            {ValloxServiceArgument.PROFILE: "home", ValloxServiceArgument.DURATION: 15},
            "failed_to_set_profile_for_duration",
            {"profile": "home", "duration": "15"},
            id="home_15_minutes",
        ),
        pytest.param(
            {
                ValloxServiceArgument.PROFILE: "boost",
                ValloxServiceArgument.DURATION: 20,
            },
            "failed_to_set_profile_for_duration",
            {"profile": "boost", "duration": "20"},
            id="boost_20_minutes",
        ),
        pytest.param(
            {
                ValloxServiceArgument.PROFILE: "fireplace",
                ValloxServiceArgument.DURATION: 10,
            },
            "failed_to_set_profile_for_duration",
            {"profile": "fireplace", "duration": "10"},
            id="fireplace_10_minutes",
        ),
    ],
)
async def test_set_profile_error(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    service_data: dict[str, str | int],
    translation_key: str,
    translation_placeholders: dict[str, str],
) -> None:
    """Test error handling when activating a profile fails."""
    mock_vallox_client.set_profile.side_effect = ValloxApiException("API error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN, ValloxService.SET_PROFILE, service_data, blocking=True
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == translation_placeholders
    # Nothing changed, so there is no refresh after the fetch at setup.
    mock_vallox_client.fetch_metric_data.assert_called_once()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("preset_mode", "profile", "time_limit_data", "expected_duration"),
    [
        pytest.param(
            "boost",
            Profile.BOOST,
            {ValloxServiceArgument.DURATION: {"minutes": 30}},
            30,
            id="boost",
        ),
        pytest.param(
            "fireplace",
            Profile.FIREPLACE,
            {ValloxServiceArgument.DURATION: {"minutes": 30}},
            30,
            id="fireplace",
        ),
        pytest.param(
            "extra",
            Profile.EXTRA,
            {ValloxServiceArgument.DURATION: {"minutes": 30}},
            30,
            id="extra",
        ),
        pytest.param(
            "boost",
            Profile.BOOST,
            {ValloxServiceArgument.DURATION: {"hours": 2, "minutes": 15}},
            135,
            id="hours_and_minutes",
        ),
        pytest.param(
            "boost",
            Profile.BOOST,
            {
                ValloxServiceArgument.DURATION: {
                    "minutes": PROFILE_DURATION_INDEFINITE - 1
                }
            },
            PROFILE_DURATION_INDEFINITE - 1,
            id="maximum",
        ),
        pytest.param(
            "boost",
            Profile.BOOST,
            {ValloxServiceArgument.NO_TIME_LIMIT: True},
            PROFILE_DURATION_INDEFINITE,
            id="no_time_limit",
        ),
        # Without a duration, the unit uses the one it has stored.
        pytest.param("boost", Profile.BOOST, {}, None, id="stored_duration"),
        pytest.param(
            "boost",
            Profile.BOOST,
            {ValloxServiceArgument.NO_TIME_LIMIT: False},
            None,
            id="time_limit_not_lifted",
        ),
    ],
)
async def test_set_preset_mode_with_duration(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    preset_mode: str,
    profile: Profile,
    time_limit_data: dict[str, Any],
    expected_duration: int | None,
) -> None:
    """Test the action for activating a preset with a time limit."""
    await hass.services.async_call(
        DOMAIN,
        ValloxService.SET_PRESET_MODE_WITH_DURATION,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ValloxServiceArgument.PRESET_MODE: preset_mode}
        | time_limit_data,
        blocking=True,
    )

    mock_vallox_client.set_profile.assert_called_once_with(profile, expected_duration)
    # One fetch at setup, and one refresh after the change.
    assert mock_vallox_client.fetch_metric_data.call_count == 2


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "service_data",
    [
        # Home, Away and Auto have no timer.
        pytest.param(
            {
                ValloxServiceArgument.PRESET_MODE: "home",
                ValloxServiceArgument.DURATION: {"minutes": 30},
            },
            id="preset_without_timer",
        ),
        pytest.param(
            {
                ValloxServiceArgument.PRESET_MODE: "boost",
                ValloxServiceArgument.DURATION: {"minutes": 0},
            },
            id="zero_duration",
        ),
        # The unit would take this duration as no time limit.
        pytest.param(
            {
                ValloxServiceArgument.PRESET_MODE: "boost",
                ValloxServiceArgument.DURATION: {
                    "minutes": PROFILE_DURATION_INDEFINITE
                },
            },
            id="duration_too_long",
        ),
        # The unit's timers count whole minutes.
        pytest.param(
            {
                ValloxServiceArgument.PRESET_MODE: "boost",
                ValloxServiceArgument.DURATION: {"minutes": 29, "seconds": 30},
            },
            id="seconds",
        ),
        # Only hours and minutes are accepted, so that a duration copied from
        # vallox.set_profile, where 30 means minutes, is not taken as seconds.
        pytest.param(
            {
                ValloxServiceArgument.PRESET_MODE: "boost",
                ValloxServiceArgument.DURATION: 30,
            },
            id="plain_number",
        ),
        pytest.param(
            {
                ValloxServiceArgument.PRESET_MODE: "boost",
                ValloxServiceArgument.DURATION: {"minutes": 30},
                ValloxServiceArgument.NO_TIME_LIMIT: True,
            },
            id="duration_and_no_time_limit",
        ),
    ],
)
async def test_set_preset_mode_with_duration_invalid(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    service_data: dict[str, Any],
) -> None:
    """Test that invalid input is rejected before anything is sent."""
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            ValloxService.SET_PRESET_MODE_WITH_DURATION,
            {ATTR_ENTITY_ID: FAN_ENTITY_ID} | service_data,
            blocking=True,
        )

    mock_vallox_client.set_profile.assert_not_called()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("time_limit_data", "translation_key", "translation_placeholders"),
    [
        pytest.param(
            {ValloxServiceArgument.DURATION: {"minutes": 30}},
            "failed_to_set_preset_mode_for_duration",
            {"preset_mode": "boost", "duration": "30"},
            id="duration",
        ),
        pytest.param(
            {ValloxServiceArgument.NO_TIME_LIMIT: True},
            "failed_to_set_preset_mode_without_time_limit",
            {"preset_mode": "boost"},
            id="no_time_limit",
        ),
        pytest.param(
            {},
            "failed_to_set_preset_mode",
            {"preset_mode": "boost"},
            id="stored_duration",
        ),
    ],
)
async def test_set_preset_mode_with_duration_error(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    time_limit_data: dict[str, Any],
    translation_key: str,
    translation_placeholders: dict[str, str],
) -> None:
    """Test error handling when activating a preset with a time limit fails."""
    mock_vallox_client.set_profile.side_effect = ValloxApiException("API error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ValloxService.SET_PRESET_MODE_WITH_DURATION,
            {ATTR_ENTITY_ID: FAN_ENTITY_ID, ValloxServiceArgument.PRESET_MODE: "boost"}
            | time_limit_data,
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == translation_placeholders
    # Nothing changed, so there is no refresh after the fetch at setup.
    mock_vallox_client.fetch_metric_data.assert_called_once()
