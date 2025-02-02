"""Test the Electric Kiwi init."""

import http
from unittest.mock import patch

from aiohttp import RequestInfo
from aiohttp.client_exceptions import ClientResponseError
import pytest

from homeassistant.components.electric_kiwi.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup, init_integration

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, component_setup: ComponentSetup
) -> None:
    """Test a successful setup entry and unload of entry."""
    await init_integration(hass, config_entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_multiple_entries(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_entry2: MockConfigEntry,
    component_setup: ComponentSetup,
) -> None:
    """Test a successful setup and unload of multiple entries."""

    for entry in (config_entry, config_entry2):
        await init_integration(hass, entry)
        assert config_entry.state is ConfigEntryState.LOADED

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2

    for entry in (config_entry, config_entry2):
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.NOT_LOADED

    assert not hass.data.get(DOMAIN)


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        (
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["failure_requires_reauth", "transient_failure"],
)
async def test_refresh_token_validity_failures(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
    component_setup: ComponentSetup,
) -> None:
    """Test token refresh failure status."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientResponseError(
            RequestInfo("", "POST", {}, ""), None, status=status
        ),
    ) as mock_async_ensure_token_valid:
        await init_integration(hass, config_entry)
        mock_async_ensure_token_valid.assert_called_once()

        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

        entries = hass.config_entries.async_entries(DOMAIN)
        assert entries[0].state is expected_state


async def test_unique_id_migration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    component_setup: ComponentSetup,
) -> None:
    """Test that the unique ID is migrated to the customer number."""
    await component_setup()
    new_entry = hass.config_entries.async_get_entry(config_entry.entry_id)
    assert new_entry.minor_version == 2
    assert new_entry.unique_id == "123456"
