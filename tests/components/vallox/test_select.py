"""Tests for Vallox select platform."""
import pytest
from vallox_websocket_api import PROFILE as VALLOX_PROFILE

from homeassistant.components.select.const import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import patch_metrics, patch_profile, patch_profile_set

from tests.common import MockConfigEntry

VALLOX_PROFILE_ENTITY_ID = "select.vallox_profile"


@pytest.mark.parametrize(
    "profile, expected_state",
    [
        (VALLOX_PROFILE.HOME, "Home"),
        (VALLOX_PROFILE.AWAY, "Away"),
        (VALLOX_PROFILE.BOOST, "Boost"),
        (VALLOX_PROFILE.FIREPLACE, "Fireplace"),
    ],
)
async def test_select_profile_entitity(
    profile: VALLOX_PROFILE,
    expected_state: str,
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
):
    """Test profile state."""
    # Act
    with patch_profile(profile=profile), patch_metrics(metrics={}):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get(VALLOX_PROFILE_ENTITY_ID)
    assert sensor.state == expected_state


async def test_select_profile_entitity_set(
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
):
    """Test profile set state."""
    # Act
    with patch_profile(profile=VALLOX_PROFILE.AWAY), patch_metrics(
        metrics={}
    ), patch_profile_set() as profile_set:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            service_data={
                ATTR_ENTITY_ID: VALLOX_PROFILE_ENTITY_ID,
                ATTR_OPTION: "Fireplace",
            },
        )
        await hass.async_block_till_done()
        profile_set.assert_called_once_with(VALLOX_PROFILE.FIREPLACE)
