"""Tests for the Vallox integration."""

import pytest
from vallox_websocket_api import Profile

from homeassistant.components.vallox import (
    ATTR_PROFILE_FAN_SPEED,
    SERVICE_SET_PROFILE_FAN_SPEED_AWAY,
    SERVICE_SET_PROFILE_FAN_SPEED_BOOST,
    SERVICE_SET_PROFILE_FAN_SPEED_HOME,
)
from homeassistant.components.vallox.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import patch_set_fan_speed

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
