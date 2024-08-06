"""Test the Reolink select platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from reolink_aio.api import Chime
from reolink_aio.exceptions import InvalidParameterError, ReolinkError

from homeassistant.components.reolink.const import DOMAIN as REOLINK_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_NVR_NAME

from tests.common import MockConfigEntry


async def test_chime_play_action_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test chime select entity."""
    TEST_CHIME = Chime(
        host=reolink_connect,
        dev_id=12345678,
        channel=0,
    )
    TEST_CHIME.name = "Test chime"
    TEST_CHIME.volume = 3
    TEST_CHIME.led_state = True
    TEST_CHIME.event_info = {
        "md": {"switch": 0, "musicId": 0},
        "people": {"switch": 0, "musicId": 1},
        "visitor": {"switch": 1, "musicId": 2},
    }

    reolink_connect.chime_list = [TEST_CHIME]
    reolink_connect.chime.return_value = TEST_CHIME

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is True
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SELECT}.test_chime_visitor_ringtone"
    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    device_id = entity.device_id

    # Test chime play action with entity
    TEST_CHIME.play = AsyncMock()
    await hass.services.async_call(
        REOLINK_DOMAIN,
        "chime_play",
        {ATTR_ENTITY_ID: [entity_id], "ringtone": "attraction"},
        blocking=True,
    )
    TEST_CHIME.play.assert_called_once()

    # Test chime play action with device
    TEST_CHIME.play = AsyncMock()
    await hass.services.async_call(
        REOLINK_DOMAIN,
        "chime_play",
        {ATTR_DEVICE_ID: [device_id], "ringtone": "attraction"},
        blocking=True,
    )
    TEST_CHIME.play.assert_called_once()

    # Test errors
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            REOLINK_DOMAIN,
            "chime_play",
            {ATTR_DEVICE_ID: ["invalid_id"], "ringtone": "attraction"},
            blocking=True,
        )

    entity_id_non_chime = f"{Platform.SELECT}.{TEST_NVR_NAME}_floodlight_mode"
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            REOLINK_DOMAIN,
            "chime_play",
            {ATTR_ENTITY_ID: [entity_id_non_chime], "ringtone": "attraction"},
            blocking=True,
        )

    TEST_CHIME.play = AsyncMock(side_effect=ReolinkError("Test error"))
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            REOLINK_DOMAIN,
            "chime_play",
            {ATTR_ENTITY_ID: [entity_id], "ringtone": "attraction"},
            blocking=True,
        )

    TEST_CHIME.play = AsyncMock(side_effect=InvalidParameterError("Test error"))
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            REOLINK_DOMAIN,
            "chime_play",
            {ATTR_ENTITY_ID: [entity_id], "ringtone": "attraction"},
            blocking=True,
        )
