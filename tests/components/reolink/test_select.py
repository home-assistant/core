"""Test the Reolink select platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
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

from .conftest import TEST_NVR_NAME

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_floodlight_mode_select(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test select entity with floodlight_mode."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SELECT}.{TEST_NVR_NAME}_floodlight_mode"
    assert hass.states.get(entity_id).state == "auto"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": "off"},
        blocking=True,
    )
    reolink_connect.set_whiteled.assert_called_once()

    reolink_connect.set_whiteled.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": "off"},
            blocking=True,
        )

    reolink_connect.set_whiteled.side_effect = InvalidParameterError("Test error")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": "off"},
            blocking=True,
        )

    reolink_connect.whiteled_mode.return_value = -99  # invalid value
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    reolink_connect.set_whiteled.reset_mock(side_effect=True)


async def test_play_quick_reply_message(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test select play_quick_reply_message entity."""
    reolink_connect.quick_reply_dict.return_value = {0: "off", 1: "test message"}
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SELECT}.{TEST_NVR_NAME}_play_quick_reply_message"
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": "test message"},
        blocking=True,
    )
    reolink_connect.play_quick_reply.assert_called_once()

    reolink_connect.quick_reply_dict = MagicMock()


async def test_host_scene_select(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test host select entity with scene mode."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SELECT}.{TEST_NVR_NAME}_scene_mode"
    assert hass.states.get(entity_id).state == "off"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": "home"},
        blocking=True,
    )
    reolink_connect.baichuan.set_scene.assert_called_once()

    reolink_connect.baichuan.set_scene.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": "home"},
            blocking=True,
        )

    reolink_connect.baichuan.set_scene.side_effect = InvalidParameterError("Test error")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": "home"},
            blocking=True,
        )

    reolink_connect.baichuan.active_scene = "Invalid value"
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    reolink_connect.baichuan.set_scene.reset_mock(side_effect=True)
    reolink_connect.baichuan.active_scene = "off"


async def test_chime_select(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    test_chime: Chime,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test chime select entity."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SELECT}.test_chime_visitor_ringtone"
    assert hass.states.get(entity_id).state == "pianokey"

    # Test selecting chime ringtone option
    test_chime.set_tone = AsyncMock()
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": "off"},
        blocking=True,
    )
    test_chime.set_tone.assert_called_once()

    test_chime.set_tone.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": "off"},
            blocking=True,
        )

    test_chime.set_tone.side_effect = InvalidParameterError("Test error")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": "off"},
            blocking=True,
        )

    # Test unavailable
    test_chime.event_info = {}
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    test_chime.set_tone.reset_mock(side_effect=True)
