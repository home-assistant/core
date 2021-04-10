"""Tests for the Sonsrr integration."""
from unittest.mock import patch

from homeassistant.components.sonarr.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_ERROR,
    ENTRY_STATE_SETUP_RETRY,
    SOURCE_REAUTH,
)
from homeassistant.const import CONF_SOURCE
from homeassistant.core import HomeAssistant

from tests.components.sonarr import setup_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_config_entry_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the configuration entry not ready."""
    entry = await setup_integration(hass, aioclient_mock, connection_error=True)
    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_config_entry_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the configuration entry needing to be re-authenticated."""
    with patch.object(hass.config_entries.flow, "async_init") as mock_flow_init:
        entry = await setup_integration(hass, aioclient_mock, invalid_auth=True)

    assert entry.state == ENTRY_STATE_SETUP_ERROR

    mock_flow_init.assert_called_once_with(
        DOMAIN,
        context={
            CONF_SOURCE: SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )


async def test_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the configuration entry unloading."""
    with patch(
        "homeassistant.components.sonarr.sensor.async_setup_entry",
        return_value=True,
    ):
        entry = await setup_integration(hass, aioclient_mock)

    assert hass.data[DOMAIN]
    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state == ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state == ENTRY_STATE_NOT_LOADED
