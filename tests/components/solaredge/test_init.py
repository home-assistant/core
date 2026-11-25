"""Tests for the SolarEdge integration."""

from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.recorder import Recorder
from homeassistant.components.solaredge.const import CONF_SITE_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import API_KEY, PASSWORD, SITE_ID, USERNAME


@patch(
    "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
    return_value=True,
)
async def test_setup_unload_api_key(
    mock_unload_platforms: AsyncMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    solaredge_api: Mock,
) -> None:
    """Test successful setup and unload of a config entry with API key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SITE_ID: SITE_ID, CONF_API_KEY: API_KEY},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert solaredge_api.get_details.await_count == 2

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Unloading should be attempted because sensors were set up.
    mock_unload_platforms.assert_awaited_once()
    assert entry.state is ConfigEntryState.NOT_LOADED


@patch(
    "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
    return_value=True,
)
async def test_setup_unload_web_login(
    mock_unload_platforms: AsyncMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    solaredge_web_api: AsyncMock,
) -> None:
    """Test successful setup and unload of a config entry with web login."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: SITE_ID,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    solaredge_web_api.async_get_equipment.assert_awaited_once()
    solaredge_web_api.async_get_energy_data.assert_awaited_once()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Unloading should NOT be attempted because sensors were not set up.
    mock_unload_platforms.assert_not_called()
    assert entry.state is ConfigEntryState.NOT_LOADED


@patch(
    "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
    return_value=True,
)
async def test_setup_unload_both(
    mock_unload_platforms: AsyncMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    solaredge_api: Mock,
    solaredge_web_api: AsyncMock,
) -> None:
    """Test successful setup and unload of a config entry with both auth methods."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: SITE_ID,
            CONF_API_KEY: API_KEY,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert solaredge_api.get_details.await_count == 2
    solaredge_web_api.async_get_equipment.assert_awaited_once()
    solaredge_web_api.async_get_energy_data.assert_awaited_once()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    mock_unload_platforms.assert_awaited_once()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_api_key_config_not_ready(
    recorder_mock: Recorder, hass: HomeAssistant, solaredge_api: Mock
) -> None:
    """Test for setup failure with API key."""
    solaredge_api.get_details.side_effect = ClientError()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SITE_ID: SITE_ID, CONF_API_KEY: API_KEY},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_web_login_config_not_ready(
    recorder_mock: Recorder, hass: HomeAssistant, solaredge_web_api: AsyncMock
) -> None:
    """Test for setup failure with web login."""
    solaredge_web_api.async_get_equipment.side_effect = ClientError()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: SITE_ID,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("get_details_response", "expected_state"),
    [
        # Missing 'details' key → ConfigEntryNotReady → SETUP_RETRY
        ({}, ConfigEntryState.SETUP_RETRY),
        # Site status is not 'active' → ConfigEntryError → SETUP_ERROR
        ({"details": {"status": "Disabled"}}, ConfigEntryState.SETUP_ERROR),
    ],
    ids=["missing_details_key", "site_not_active"],
)
async def test_setup_api_key_failure(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
    get_details_response: dict,
    expected_state: ConfigEntryState,
) -> None:
    """Test the API-key setup failure paths in async_setup_entry."""
    solaredge_api.get_details.return_value = get_details_response

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_setup_site_not_active(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
) -> None:
    """Test the setup error reason when the site is not active."""
    solaredge_api.get_details.return_value = {"details": {"status": "Disabled"}}

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == "The SolarEdge site is not active"


async def test_remove_device(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
) -> None:
    """Test removing a device is only allowed when no API key is configured."""
    assert await async_setup_component(hass, "config", {})
    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, SITE_ID), mock_config_entry.entry_id
    )
    assert device_entry is not None

    client = await hass_ws_client(hass)

    # Cannot remove the device while the API key is configured.
    response = await client.remove_device(device_entry.id)
    assert not response["success"]
    assert device_registry.async_get(device_entry.id) is not None

    # After removing the API key (switching to web login only), the device can be removed.
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            CONF_SITE_ID: SITE_ID,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    response = await client.remove_device(device_entry.id)
    assert response["success"]
    assert device_registry.async_get(device_entry.id) is None
