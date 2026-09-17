"""Test the Discord integration setup."""

import nextcord

from homeassistant.components.discord.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    TARGET_NAME,
    create_entry,
    mock_exception,
    patch_discord_login,
    setup_integration,
)
from .conftest import TARGET


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    """Test the config entry sets up and unloads."""
    entry = create_entry(hass, with_subentry=True)
    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_auth_failed(hass: HomeAssistant) -> None:
    """Test the config entry fails to authenticate."""
    entry = create_entry(hass)
    with patch_discord_login() as mock:
        mock.side_effect = nextcord.LoginFailure
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_cannot_connect(hass: HomeAssistant) -> None:
    """Test the config entry retries when it cannot connect."""
    entry = create_entry(hass)
    with patch_discord_login() as mock:
        mock.side_effect = mock_exception()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_notify_entity_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a notify entity and its devices are created for a target subentry."""
    entry = create_entry(hass, with_subentry=True)
    await setup_integration(hass, entry)

    subentry_id = next(iter(entry.subentries))

    entity_entry = entity_registry.async_get(f"notify.{TARGET_NAME}")
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{entry.entry_id}_{int(TARGET)}"
    assert entity_entry.config_subentry_id == subentry_id

    bot_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert bot_device is not None

    channel_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry.entry_id}_{int(TARGET)}"), entry.entry_id
    )
    assert channel_device is not None
    assert channel_device.via_device_id == bot_device.id
