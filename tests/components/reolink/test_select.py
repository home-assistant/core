"""Test the Reolink select platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from reolink_aio.api import Chime
from reolink_aio.exceptions import InvalidParameterError, ReolinkError

from homeassistant.components.reolink import DEVICE_UPDATE_INTERVAL
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_SELECT_OPTION,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .conftest import TEST_NVR_NAME

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_floodlight_mode_select(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test select entity with floodlight_mode."""
    reolink_connect.whiteled_mode.return_value = 1
    reolink_connect.whiteled_mode_list.return_value = ["off", "auto"]
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is True
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SELECT}.{TEST_NVR_NAME}_floodlight_mode"
    assert hass.states.is_state(entity_id, "auto")

    reolink_connect.set_whiteled = AsyncMock()
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": "off"},
        blocking=True,
    )
    reolink_connect.set_whiteled.assert_called_once()

    reolink_connect.set_whiteled = AsyncMock(side_effect=ReolinkError("Test error"))
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": "off"},
            blocking=True,
        )

    reolink_connect.set_whiteled = AsyncMock(
        side_effect=InvalidParameterError("Test error")
    )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": "off"},
            blocking=True,
        )


async def test_play_quick_reply_message(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test select play_quick_reply_message entity."""
    reolink_connect.quick_reply_dict.return_value = {0: "off", 1: "test message"}
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is True
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SELECT}.{TEST_NVR_NAME}_play_quick_reply_message"
    assert hass.states.is_state(entity_id, STATE_UNKNOWN)

    reolink_connect.play_quick_reply = AsyncMock()
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": "test message"},
        blocking=True,
    )
    reolink_connect.play_quick_reply.assert_called_once()


async def test_chime_select(
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
        name="Test chime",
        event_info={
            "md": {"switch": 0, "musicId": 0},
            "people": {"switch": 0, "musicId": 1},
            "visitor": {"switch": 1, "musicId": 2},
        },
    )
    TEST_CHIME.volume = 3
    TEST_CHIME.led_state = True

    reolink_connect.chime_list = [TEST_CHIME]

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is True
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SELECT}.test_chime_visitor_ringtone"
    assert hass.states.is_state(entity_id, "pianokey")

    TEST_CHIME.set_tone = AsyncMock()
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": "off"},
        blocking=True,
    )
    TEST_CHIME.set_tone.assert_called_once()

    TEST_CHIME.set_tone = AsyncMock(side_effect=ReolinkError("Test error"))
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": "off"},
            blocking=True,
        )

    TEST_CHIME.set_tone = AsyncMock(side_effect=InvalidParameterError("Test error"))
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": "off"},
            blocking=True,
        )

    TEST_CHIME.event_info = {}
    async_fire_time_changed(
        hass, utcnow() + DEVICE_UPDATE_INTERVAL + timedelta(seconds=30)
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(entity_id, STATE_UNKNOWN)
