"""Tests for Vallox services."""

import pytest
from vallox_websocket_api import Profile, ValloxApiException

from homeassistant.components.vallox.const import DOMAIN, I18N_KEY_TO_VALLOX_PROFILE
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
    ("service", "profile"),
    [
        (ValloxService.SET_PROFILE_FAN_SPEED_HOME, Profile.HOME),
        (ValloxService.SET_PROFILE_FAN_SPEED_AWAY, Profile.AWAY),
        (ValloxService.SET_PROFILE_FAN_SPEED_BOOST, Profile.BOOST),
    ],
)
async def test_set_profile_fan_speed_error(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    service: str,
    profile: Profile,
) -> None:
    """Test error handling when setting fan speed fails."""
    # Act
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

        # Assert
        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "failed_to_set_fan_speed_for_profile"
        assert exc_info.value.translation_placeholders == {
            "profile": profile.name,
            "fan_speed": "30",
        }


@pytest.mark.parametrize(
    ("profile", "duration", "expected_key"),
    [
        ("home", None, "failed_to_set_profile"),
        ("home", 65535, "failed_to_set_profile"),
        ("home", 15, "failed_to_set_profile_for_duration"),
        ("boost", None, "failed_to_set_profile"),
        ("boost", 65535, "failed_to_set_profile"),
        ("boost", 20, "failed_to_set_profile_for_duration"),
        ("fireplace", 10, "failed_to_set_profile_for_duration"),
        ("extra", None, "failed_to_set_profile"),
    ],
)
async def test_set_profile_error(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    profile: str,
    duration: int | None,
    expected_key: str,
) -> None:
    """Test error handling when setting profile fails."""
    # Act
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

        # Assert
        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == expected_key

        if expected_key == "failed_to_set_profile_for_duration":
            assert exc_info.value.translation_placeholders == {
                "profile": profile,
                "duration": str(duration),
            }
        else:
            assert exc_info.value.translation_placeholders == {"profile": profile}
