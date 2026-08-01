"""Test the Netis Router integration setup, unload and services."""

from __future__ import annotations

import pytest

from homeassistant.components.netis import DOMAIN
from homeassistant.components.netis.api import NetisError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("init_integration")
async def test_setup_entry_loaded(hass: HomeAssistant) -> None:
    """The integration should reach LOADED state on successful setup."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("init_integration")
async def test_services_registered(hass: HomeAssistant) -> None:
    """Both custom services should be registered after setup."""
    assert hass.services.has_service(DOMAIN, "send_sms")
    assert hass.services.has_service(DOMAIN, "set_speed_limit")


@pytest.mark.usefixtures("init_integration")
async def test_send_sms_service_calls_client(
    hass: HomeAssistant, mock_netis_client
) -> None:
    """netis.send_sms should forward arguments to the API client."""
    await hass.services.async_call(
        DOMAIN,
        "send_sms",
        {"phone": "13800138000", "message": "Hello"},
        blocking=True,
    )
    mock_netis_client.send_sms.assert_awaited_once_with("13800138000", "Hello")


@pytest.mark.usefixtures("init_integration")
async def test_set_speed_limit_service_calls_client(
    hass: HomeAssistant, mock_netis_client
) -> None:
    """netis.set_speed_limit should forward mac + speeds to the client."""
    await hass.services.async_call(
        DOMAIN,
        "set_speed_limit",
        {"mac": "aa:bb:cc:dd:ee:ff", "down_speed": 1024, "up_speed": 512},
        blocking=True,
    )
    mock_netis_client.set_speed_limit.assert_awaited_once_with(
        "aa:bb:cc:dd:ee:ff", 1024, 512
    )


@pytest.mark.usefixtures("init_integration")
async def test_unload_entry(hass: HomeAssistant, mock_netis_client) -> None:
    """Unloading should tear down platforms and remove services."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    # Services removed when the last entry is unloaded.
    assert not hass.services.has_service(DOMAIN, "send_sms")
    assert not hass.services.has_service(DOMAIN, "set_speed_limit")


async def test_setup_retry_on_api_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_netis_client,
) -> None:
    """A failing first refresh should put the entry into SETUP_RETRY.

    Does NOT use ``init_integration`` (which would succeed) — this test
    drives setup itself with a failing ``gather``.
    """
    mock_netis_client.gather.side_effect = NetisError("boom")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
