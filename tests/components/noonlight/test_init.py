"""Setup tests: test-before-setup connectivity probe.

(ConfigEntryNotReady / ConfigEntryAuthFailed)
"""

from unittest.mock import patch

import httpx
from httpx import Response
import respx

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@respx.mock
async def test_setup_retries_on_connection_error(
    hass: HomeAssistant, config_entry
) -> None:
    """A transport failure on the probe leaves the entry in SETUP_RETRY."""
    respx.get(url__regex=r".*/dispatch/v1/alarms/.*/status").mock(
        side_effect=httpx.ConnectError("down")
    )

    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@respx.mock
async def test_setup_auth_error_on_401(hass: HomeAssistant, config_entry) -> None:
    """A 401 on the probe surfaces as an auth failure (reauth)."""
    respx.get(url__regex=r".*/dispatch/v1/alarms/.*/status").mock(
        return_value=Response(401)
    )

    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


@respx.mock
async def test_setup_retries_on_unexpected_response(
    hass: HomeAssistant, config_entry
) -> None:
    """A non-404 error response (e.g. 500) is treated as not-ready."""
    respx.get(url__regex=r".*/dispatch/v1/alarms/.*/status").mock(
        return_value=Response(500)
    )

    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@respx.mock
async def test_setup_succeeds_on_404_probe(hass: HomeAssistant, config_entry) -> None:
    """A 404 means reachable + authorised, so setup completes."""
    respx.get(url__regex=r".*/dispatch/v1/alarms/.*/status").mock(
        return_value=Response(404)
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


async def test_unload_reports_failure_when_platform_unload_fails(
    hass: HomeAssistant, setup_entry
) -> None:
    """If a platform fails to unload, the entry unload reports failure."""
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(setup_entry.entry_id)
