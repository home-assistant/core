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
from homeassistant.helpers import entity_registry as er, issue_registry as ir

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


@pytest.mark.parametrize(
    (
        "original_id",
        "capability",
    ),
    [
        (
            f"{TEST_UID}_record",
            "recording",
        ),
        (
            f"{TEST_UID}_ftp_upload",
            "ftp",
        ),
        (
            f"{TEST_UID}_push_notifications",
            "push",
        ),
        (
            f"{TEST_UID}_email",
            "email",
        ),
        (
            f"{TEST_UID}_buzzer",
            "buzzer",
        ),
    ],
)
async def test_cleanup_hub_switches(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
    entity_registry: er.EntityRegistry,
    original_id: str,
    capability: str,
) -> None:
    """Test entity ids that need to be migrated."""

    def mock_supported(ch, cap):
        if cap == capability:
            return False
        return True

    domain = Platform.SWITCH

    reolink_host.channels = [0]
    reolink_host.is_hub = True
    reolink_host.supported = mock_supported

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


@pytest.mark.parametrize(
    (
        "original_id",
        "capability",
    ),
    [
        (
            f"{TEST_UID}_record",
            "recording",
        ),
        (
            f"{TEST_UID}_ftp_upload",
            "ftp",
        ),
        (
            f"{TEST_UID}_push_notifications",
            "push",
        ),
        (
            f"{TEST_UID}_email",
            "email",
        ),
        (
            f"{TEST_UID}_buzzer",
            "buzzer",
        ),
    ],
)
async def test_hub_switches_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    original_id: str,
    capability: str,
) -> None:
    """Test entity ids that need to be migrated."""

    def mock_supported(ch, cap):
        if cap == capability:
            return False
        return True

    domain = Platform.SWITCH

    reolink_host.channels = [0]
    reolink_host.is_hub = True
    reolink_host.supported = mock_supported

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
    assert (DOMAIN, "hub_switch_deprecated") in issue_registry.issues
