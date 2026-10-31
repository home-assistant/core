"""Tests for the Vallox services."""

from unittest.mock import AsyncMock

import pytest
from vallox_websocket_api import Profile, ValloxApiException

from homeassistant.components.vallox.const import DOMAIN, PROFILE_DURATION_INDEFINITE
from homeassistant.components.vallox.services import (
    ATTR_DURATION,
    ATTR_PROFILE,
    ATTR_PROFILE_FAN_SPEED,
    ValloxService,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


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
        DOMAIN, service, {ATTR_PROFILE_FAN_SPEED: 30}, blocking=True
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
        {ATTR_PROFILE_FAN_SPEED: fan_speed},
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
        pytest.param({ATTR_DURATION: 15}, 15, id="15_minutes"),
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
        {ATTR_PROFILE: profile_key} | duration_data,
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
        {ATTR_PROFILE: "boost", ATTR_DURATION: duration},
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
            DOMAIN, service, {ATTR_PROFILE_FAN_SPEED: 30}, blocking=True
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
            {ATTR_PROFILE: "home"},
            "failed_to_set_profile",
            {"profile": "home"},
            id="home",
        ),
        pytest.param(
            {ATTR_PROFILE: "home", ATTR_DURATION: PROFILE_DURATION_INDEFINITE},
            "failed_to_set_profile",
            {"profile": "home"},
            id="home_indefinite",
        ),
        pytest.param(
            {ATTR_PROFILE: "boost"},
            "failed_to_set_profile",
            {"profile": "boost"},
            id="boost",
        ),
        pytest.param(
            {ATTR_PROFILE: "boost", ATTR_DURATION: PROFILE_DURATION_INDEFINITE},
            "failed_to_set_profile",
            {"profile": "boost"},
            id="boost_indefinite",
        ),
        pytest.param(
            {ATTR_PROFILE: "extra"},
            "failed_to_set_profile",
            {"profile": "extra"},
            id="extra",
        ),
        pytest.param(
            {ATTR_PROFILE: "home", ATTR_DURATION: 15},
            "failed_to_set_profile_for_duration",
            {"profile": "home", "duration": "15"},
            id="home_15_minutes",
        ),
        pytest.param(
            {ATTR_PROFILE: "boost", ATTR_DURATION: 20},
            "failed_to_set_profile_for_duration",
            {"profile": "boost", "duration": "20"},
            id="boost_20_minutes",
        ),
        pytest.param(
            {ATTR_PROFILE: "fireplace", ATTR_DURATION: 10},
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
