"""Test the Reolink switch platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from reolink_aio.api import Chime
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.reolink import DEVICE_UPDATE_INTERVAL
from homeassistant.components.reolink.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import TEST_CAM_NAME, TEST_NVR_NAME, TEST_UID

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    reolink_host: MagicMock,
) -> None:
    """Test switch entity."""
    reolink_host.audio_record.return_value = True

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SWITCH}.{TEST_CAM_NAME}_record_audio"
    assert hass.states.get(entity_id).state == STATE_ON

    reolink_host.audio_record.return_value = False
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF

    # test switch turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_host.set_audio.assert_called_with(0, True)

    reolink_host.set_audio.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    # test switch turn off
    reolink_host.set_audio.reset_mock(side_effect=True)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_host.set_audio.assert_called_with(0, False)

    reolink_host.set_audio.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    reolink_host.set_audio.reset_mock(side_effect=True)

    reolink_host.camera_online.return_value = False
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_host_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    reolink_host: MagicMock,
) -> None:
    """Test host switch entity."""
    reolink_host.email_enabled.return_value = True
    reolink_host.is_hub = False
    reolink_host.supported.return_value = True

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SWITCH}.{TEST_NVR_NAME}_email_on_event"
    assert hass.states.get(entity_id).state == STATE_ON

    reolink_host.email_enabled.return_value = False
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF

    # test switch turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_host.set_email.assert_called_with(None, True)

    reolink_host.set_email.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    # test switch turn off
    reolink_host.set_email.reset_mock(side_effect=True)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_host.set_email.assert_called_with(None, False)

    reolink_host.set_email.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


@pytest.mark.parametrize("channel", [0, None])
async def test_chime_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    reolink_host: MagicMock,
    reolink_chime: Chime,
    channel: int | None,
) -> None:
    """Test host switch entity."""
    reolink_chime.channel = channel

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SWITCH}.test_chime_led"
    assert hass.states.get(entity_id).state == STATE_ON

    reolink_chime.led_state = False
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF

    # test switch turn on
    reolink_chime.set_option = AsyncMock()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_chime.set_option.assert_called_with(led=True)

    reolink_chime.set_option.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    # test switch turn off
    reolink_chime.set_option.reset_mock(side_effect=True)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_chime.set_option.assert_called_with(led=False)

    reolink_chime.set_option.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
