"""Test the Aussie Broadband init."""

from unittest.mock import patch

from aiohttp import ClientConnectionError
from aussiebb.exceptions import AuthenticationException, UnrecognisedServiceType

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import setup_platform


async def test_unload(hass: HomeAssistant) -> None:
    """Test unload."""
    entry = await setup_platform(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_auth_failure(hass: HomeAssistant) -> None:
    """Test init with an authentication failure."""
    with patch(
        "homeassistant.components.aussie_broadband.config_flow.AussieBroadbandConfigFlow.async_step_reauth",
        return_value={
            "type": FlowResultType.FORM,
            "flow_id": "mock_flow",
            "step_id": "reauth_confirm",
        },
    ) as mock_async_step_reauth:
        await setup_platform(hass, side_effect=AuthenticationException())
        mock_async_step_reauth.assert_called_once()


async def test_net_failure(hass: HomeAssistant) -> None:
    """Test init with a network failure."""
    entry = await setup_platform(hass, side_effect=ClientConnectionError())
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_service_failure(hass: HomeAssistant) -> None:
    """Test init with a invalid service."""
    entry = await setup_platform(hass, usage_effect=UnrecognisedServiceType())
    assert entry.state is ConfigEntryState.SETUP_RETRY
