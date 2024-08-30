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
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .conftest import TEST_CAM_NAME, TEST_NVR_NAME, TEST_UID

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_cleanup_hdr_switch_(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test cleanup of the HDR switch entity."""
    original_id = f"{TEST_UID}_hdr"
    domain = Platform.SWITCH

    reolink_connect.channels = [0]
    reolink_connect.supported.return_value = True

    entity_registry.async_get_or_create(
        domain=domain,
        platform=DOMAIN,
        unique_id=original_id,
        config_entry=config_entry,
        suggested_object_id=original_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    assert entity_registry.async_get_entity_id(domain, DOMAIN, original_id)

    # setup CH 0 and host entities/device
    with patch("homeassistant.components.reolink.PLATFORMS", [domain]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id(domain, DOMAIN, original_id) is None


async def test_hdr_switch_deprecated_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repairs issue is raised when hdr switch entity used."""
    original_id = f"{TEST_UID}_hdr"
    domain = Platform.SWITCH

    reolink_connect.channels = [0]
    reolink_connect.supported.return_value = True

    entity_registry.async_get_or_create(
        domain=domain,
        platform=DOMAIN,
        unique_id=original_id,
        config_entry=config_entry,
        suggested_object_id=original_id,
        disabled_by=None,
    )

    assert entity_registry.async_get_entity_id(domain, DOMAIN, original_id)

    # setup CH 0 and host entities/device
    with patch("homeassistant.components.reolink.PLATFORMS", [domain]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id(domain, DOMAIN, original_id)

    assert (DOMAIN, "hdr_switch_deprecated") in issue_registry.issues


async def test_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    reolink_connect: MagicMock,
) -> None:
    """Test switch entity."""
    reolink_connect.camera_name.return_value = TEST_CAM_NAME

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SWITCH}.{TEST_CAM_NAME}_record"
    assert hass.states.get(entity_id).state == STATE_ON

    reolink_connect.recording_enabled.return_value = False
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
    reolink_connect.set_recording.assert_called_with(0, True)

    reolink_connect.set_recording.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    # test switch turn off
    reolink_connect.set_recording.side_effect = None
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_connect.set_recording.assert_called_with(0, False)

    reolink_connect.set_recording.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_host_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    reolink_connect: MagicMock,
) -> None:
    """Test host switch entity."""
    reolink_connect.camera_name.return_value = TEST_CAM_NAME

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SWITCH}.{TEST_NVR_NAME}_record"
    assert hass.states.get(entity_id).state == STATE_ON

    reolink_connect.recording_enabled.return_value = False
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
    reolink_connect.set_recording.assert_called_with(None, True)

    reolink_connect.set_recording.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    # test switch turn off
    reolink_connect.set_recording.side_effect = None
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_connect.set_recording.assert_called_with(None, False)

    reolink_connect.set_recording.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_chime_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    reolink_connect: MagicMock,
    test_chime: Chime,
) -> None:
    """Test host switch entity."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SWITCH}.test_chime_led"
    assert hass.states.get(entity_id).state == STATE_ON

    test_chime.led_state = False
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF

    # test switch turn on
    test_chime.set_option = AsyncMock()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    test_chime.set_option.assert_called_with(led=True)

    test_chime.set_option.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    # test switch turn off
    test_chime.set_option.side_effect = None
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    test_chime.set_option.assert_called_with(led=False)

    test_chime.set_option.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
