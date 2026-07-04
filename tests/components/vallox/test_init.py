"""Tests for Vallox services."""

import pytest
from vallox_websocket_api import Profile, ValloxApiException

from homeassistant.components.vallox.const import (
    DOMAIN,
    I18N_KEY_TO_VALLOX_PROFILE,
    PROFILE_DURATION_INDEFINITE,
)
from homeassistant.components.vallox.services import (
    ATTR_DURATION,
    ATTR_PROFILE,
    ATTR_PROFILE_FAN_SPEED,
    ValloxService,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import patch_set_fan_speed, patch_set_profile

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("service", "profile"),
    [
        (ValloxService.SET_PROFILE_FAN_SPEED_HOME, Profile.HOME),
        (ValloxService.SET_PROFILE_FAN_SPEED_AWAY, Profile.AWAY),
        (ValloxService.SET_PROFILE_FAN_SPEED_BOOST, Profile.BOOST),
    ],
)
async def test_create_service(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    service: str,
    profile: Profile,
) -> None:
    """Test services for setting fan speed."""
    # Act
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    with patch_set_fan_speed() as set_fan_speed:
        await hass.services.async_call(
            DOMAIN,
            service,
            service_data={ATTR_PROFILE_FAN_SPEED: 30},
        )

        await hass.async_block_till_done()

        # Assert
        set_fan_speed.assert_called_once_with(profile, 30)


@pytest.mark.parametrize(
    ("profile", "duration"),
    [
        ("home", None),
        ("home", 15),
        ("away", None),
        ("away", 15),
        ("boost", None),
        ("boost", 15),
        ("fireplace", None),
        ("fireplace", 15),
        ("extra", None),
        ("extra", 15),
    ],
)
async def test_set_profile_service(
    hass: HomeAssistant, mock_entry: MockConfigEntry, profile: str, duration: int | None
) -> None:
    """Test service for setting profile and duration."""
    # Act
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    with patch_set_profile() as set_profile:
        service_data = {ATTR_PROFILE: profile} | (
            {ATTR_DURATION: duration} if duration is not None else {}
        )

        await hass.services.async_call(
            DOMAIN,
            ValloxService.SET_PROFILE,
            service_data=service_data,
        )

        await hass.async_block_till_done()

        # Assert
        set_profile.assert_called_once_with(
            I18N_KEY_TO_VALLOX_PROFILE[profile], duration
        )


@pytest.mark.parametrize(
    ("service", "expected_profile"),
    [
        (ValloxService.SET_PROFILE_FAN_SPEED_HOME, "home"),
        (ValloxService.SET_PROFILE_FAN_SPEED_AWAY, "away"),
        (ValloxService.SET_PROFILE_FAN_SPEED_BOOST, "boost"),
    ],
)
async def test_set_profile_fan_speed_error(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    service: str,
    expected_profile: str,
) -> None:
    """Test error handling when setting fan speed fails."""
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    with patch_set_fan_speed() as set_fan_speed:
        set_fan_speed.side_effect = ValloxApiException("Connection error")

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                service,
                service_data={ATTR_PROFILE_FAN_SPEED: 30},
                blocking=True,
            )

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "failed_to_set_fan_speed_for_profile"
        assert exc_info.value.translation_placeholders == {
            "profile": expected_profile,
            "fan_speed": "30",
        }


@pytest.mark.parametrize(
    ("profile", "duration"),
    [
        ("home", None),
        ("home", PROFILE_DURATION_INDEFINITE),
        ("boost", None),
        ("boost", PROFILE_DURATION_INDEFINITE),
        ("extra", None),
    ],
)
async def test_set_profile_without_duration_error(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    profile: str,
    duration: int | None,
) -> None:
    """Test error handling when setting profile with no/indefinite duration fails."""
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    with patch_set_profile() as set_profile:
        set_profile.side_effect = ValloxApiException("API error")

        service_data = {ATTR_PROFILE: profile} | (
            {ATTR_DURATION: duration} if duration is not None else {}
        )

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                ValloxService.SET_PROFILE,
                service_data=service_data,
                blocking=True,
            )

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "failed_to_set_profile"
        assert exc_info.value.translation_placeholders == {"profile": profile}


@pytest.mark.parametrize(
    ("profile", "duration"),
    [
        ("home", 15),
        ("boost", 20),
        ("fireplace", 10),
    ],
)
async def test_set_profile_with_duration_error(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    profile: str,
    duration: int | None,
) -> None:
    """Test error handling when setting profile with duration fails."""
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    with patch_set_profile() as set_profile:
        set_profile.side_effect = ValloxApiException("API error")

        service_data = {ATTR_PROFILE: profile} | ({ATTR_DURATION: duration})

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                ValloxService.SET_PROFILE,
                service_data=service_data,
                blocking=True,
            )

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "failed_to_set_profile_for_duration"
        assert exc_info.value.translation_placeholders == {
            "profile": profile,
            "duration": str(duration),
        }
