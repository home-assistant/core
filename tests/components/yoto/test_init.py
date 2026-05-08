"""Tests for the Yoto integration setup."""

import aiohttp

from homeassistant.components.yoto.coordinator import DEVICES_ENDPOINT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_unload(
    hass: HomeAssistant,
    mock_devices_endpoint: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """The integration loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_auth_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """An authentication error during refresh triggers reauth."""
    aioclient_mock.get(DEVICES_ENDPOINT, status=401, json={"message": "denied"})

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_update_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """A network failure during refresh surfaces as a setup retry."""
    aioclient_mock.get(DEVICES_ENDPOINT, exc=aiohttp.ClientError("boom"))

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_mqtt_event_dispatches_update(
    hass: HomeAssistant,
    mock_yoto_manager,
    mock_devices_endpoint: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """The coordinator's MQTT callback can be invoked safely."""
    mock_yoto_manager.mqtt_client = None

    await setup_integration(hass, mock_config_entry)

    callback = mock_yoto_manager.connect_to_events.call_args.args[0]
    callback()
    callback()
