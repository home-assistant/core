"""Tests for SpeedTest integration."""
from unittest.mock import AsyncMock

from py17track.errors import SeventeenTrackError

from homeassistant.components.seventeentrack.const import (
    CONF_ACCOUNT,
    CONF_TRACKING_NUMBER,
    DOMAIN,
    SERVICE_ADD_PACKAGE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .test_config_flow import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_setup_with_no_config(hass: HomeAssistant) -> None:
    """Test that we do not discover anything or try to set up a controller."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert DOMAIN not in hass.data


async def test_successful_config_entry(hass: HomeAssistant, mock_api) -> None:
    """Test that Seventeentrack is configured successfully."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.LOADED


async def test_add_package(hass: HomeAssistant, mock_api) -> None:
    """Test adding new package."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id="user")
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    device_registry = hass.helpers.device_registry.async_get(hass)
    device_id = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_CONFIG[CONF_USERNAME])}
    ).id

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_PACKAGE,
        {
            CONF_ACCOUNT: device_id,
            CONF_TRACKING_NUMBER: "AB123",
            CONF_FRIENDLY_NAME: "My package",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_api.assert_called_once()


async def test_setup_failed(hass: HomeAssistant, mock_api) -> None:
    """Test Seventeentrack failed due to failed authentication."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="user",
    )
    entry.add_to_hass(hass)

    mock_api.return_value.login = AsyncMock(return_value=False)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_setup_retry(hass: HomeAssistant, mock_api) -> None:
    """Test Seventeentrack setup retry due to unknown error."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="user",
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = SeventeenTrackError
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing Seventeentrack."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
