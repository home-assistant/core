"""Tests for init module."""
from asyncio.exceptions import TimeoutError
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import async_get

from .const import (
    AUTOMER_SM_CONFIG,
    AUTOMOWER_CONFIG_DATA,
    AUTOMOWER_CONFIG_DATA_BAD_SCOPE,
    AUTOMOWER_SM_SESSION_DATA,
)

from tests.common import MockConfigEntry


async def configure_application_credentials(hass: HomeAssistant):
    """Configure application credentials."""
    app_cred_config_entry = MockConfigEntry(
        domain="application_credentials",
        data={},
        entry_id="application_credentials",
        title="Application Credentials",
    )
    app_cred_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(app_cred_config_entry.entry_id)

    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(
            "test_client_id",
            "test_config_secret",
        ),
    )


@pytest.mark.asyncio
async def test_load_unload(hass: HomeAssistant) -> None:
    """Test automower initialization."""

    await configure_application_credentials(hass)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=AUTOMOWER_CONFIG_DATA,
        options=AUTOMER_SM_CONFIG,
        entry_id="automower_test",
        title="Automower Test",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "aioautomower.session.AutomowerSession",
        return_value=AsyncMock(
            register_token_callback=MagicMock(),
            connect=AsyncMock(),
            close=AsyncMock(),
            data=AUTOMOWER_SM_SESSION_DATA,
            register_data_callback=MagicMock(),
            unregister_data_callback=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

        assert await config_entry.async_unload(hass)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.NOT_LOADED

    with patch(
        "aioautomower.session.AutomowerSession",
        return_value=AsyncMock(
            register_token_callback=MagicMock(),
            connect=AsyncMock(side_effect=TimeoutError),
        ),
    ):
        # Timeout Error
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.SETUP_RETRY

        assert await config_entry.async_unload(hass)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.NOT_LOADED

    with patch(
        "aioautomower.session.AutomowerSession",
        return_value=AsyncMock(
            close=AsyncMock(side_effect=Exception),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert await config_entry.async_unload(hass)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.NOT_LOADED

    with patch(
        "aioautomower.session.AutomowerSession",
        return_value=AsyncMock(
            register_token_callback=MagicMock(),
            connect=AsyncMock(side_effect=Exception("Test Exception")),
        ),
    ):
        # Generic Error
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.SETUP_ERROR


@pytest.mark.asyncio
async def test_load_unload_wrong_scope(hass: HomeAssistant) -> None:
    """Test automower initialization, wrong token scope."""

    await configure_application_credentials(hass)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=AUTOMOWER_CONFIG_DATA_BAD_SCOPE,
        options=AUTOMER_SM_CONFIG,
        entry_id="automower_test",
        title="Automower Test",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "aioautomower.session.AutomowerSession",
        return_value=AsyncMock(register_token_callback=MagicMock()),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state == ConfigEntryState.LOADED
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

        issue_registry = async_get(hass)
        issue = issue_registry.async_get_issue(DOMAIN, "wrong_scope")
        assert issue is not None

        assert await config_entry.async_unload(hass)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.NOT_LOADED
