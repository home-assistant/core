"""Tests for the everHome/EcoTracker integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.everhome.const import REQUEST_REFRESH_COOLDOWN
from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_platform

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_everhome_client")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_connection_failed(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the device is unreachable."""
    mock_everhome_client.async_update.return_value = False
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_entity_polls_every_cooldown(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update_entity polls the device once per refresh cooldown."""
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    mock_config_entry.add_to_hass(hass)
    # Without scheduled polling, only update_entity triggers refreshes.
    hass.config_entries.async_update_entry(mock_config_entry, pref_disable_polling=True)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    calls_after_setup = mock_everhome_client.async_update.call_count

    for _ in range(3):
        freezer.tick(timedelta(seconds=REQUEST_REFRESH_COOLDOWN))
        async_fire_time_changed(hass)
        await hass.services.async_call(
            HOMEASSISTANT_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: "sensor.everhome_abcdef123456_power"},
            blocking=True,
        )

    assert mock_everhome_client.async_update.call_count == calls_after_setup + 3
