"""Test the Electric Kiwi init."""

import http
from unittest.mock import AsyncMock, patch

from aiohttp import RequestInfo
from aiohttp.client_exceptions import ClientResponseError
from electrickiwi_api.exceptions import ApiException, AuthException
import pytest

from homeassistant.components.electric_kiwi.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test a successful setup entry and unload of entry."""
    await init_integration(hass, config_entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_multiple_entries(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_entry2: MockConfigEntry,
) -> None:
    """Test a successful setup and unload of multiple entries."""

    for entry in (config_entry, config_entry2):
        await init_integration(hass, entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2

    for entry in (config_entry, config_entry2):
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.NOT_LOADED


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
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the unique ID is migrated to the customer number."""

    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN, DOMAIN, "123456_515363_sensor", config_entry=config_entry
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    new_entry = hass.config_entries.async_get_entry(config_entry.entry_id)
    assert new_entry.minor_version == 2
    assert new_entry.unique_id == "123456"
    entity_entry = entity_registry.async_get(
        "sensor.electric_kiwi_123456_515363_sensor"
    )
    assert entity_entry.unique_id == "123456_00000000DDA_sensor"


async def test_unique_id_migration_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, electrickiwi_api: AsyncMock
) -> None:
    """Test that the unique ID is migrated to the customer number."""
    electrickiwi_api.set_active_session.side_effect = ApiException()
    await init_integration(hass, config_entry)

    assert config_entry.minor_version == 1
    assert config_entry.unique_id == DOMAIN
    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_unique_id_migration_auth_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, electrickiwi_api: AsyncMock
) -> None:
    """Test that the unique ID is migrated to the customer number."""
    electrickiwi_api.set_active_session.side_effect = AuthException()
    await init_integration(hass, config_entry)

    assert config_entry.minor_version == 1
    assert config_entry.unique_id == DOMAIN
    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR
