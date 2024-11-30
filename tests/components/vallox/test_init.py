"""Tests for the Vallox integration."""

import pytest
from vallox_websocket_api import Profile

from homeassistant.components.vallox import (
    ATTR_DURATION,
    ATTR_PROFILE,
    ATTR_PROFILE_FAN_SPEED,
    I18N_KEY_TO_VALLOX_PROFILE,
    SERVICE_SET_PROFILE,
    SERVICE_SET_PROFILE_FAN_SPEED_AWAY,
    SERVICE_SET_PROFILE_FAN_SPEED_BOOST,
    SERVICE_SET_PROFILE_FAN_SPEED_HOME,
)
from homeassistant.components.vallox.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import patch_set_fan_speed, patch_set_profile

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("service", "profile"),
    [
        (SERVICE_SET_PROFILE_FAN_SPEED_HOME, Profile.HOME),
        (SERVICE_SET_PROFILE_FAN_SPEED_AWAY, Profile.AWAY),
        (SERVICE_SET_PROFILE_FAN_SPEED_BOOST, Profile.BOOST),
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
            SERVICE_SET_PROFILE,
            service_data=service_data,
        )

        await hass.async_block_till_done()

        # Assert
        set_profile.assert_called_once_with(
            I18N_KEY_TO_VALLOX_PROFILE[profile], duration
        )
