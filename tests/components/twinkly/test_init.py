"""Tests of the initialization of the twinkly integration."""

from unittest.mock import AsyncMock

from aiohttp import ClientConnectionError
import pytest

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.twinkly.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .const import TEST_MAC, TEST_MODEL

from tests.common import MockConfigEntry, async_load_json_object_fixture


@pytest.mark.usefixtures("mock_twinkly_client")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the load/unload of the config entry."""

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Validate that config entry is retried."""
    mock_twinkly_client.get_details.side_effect = ClientConnectionError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_twinkly_client")
async def test_mac_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Validate that the unique_id is migrated to the MAC address."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        minor_version=1,
        unique_id="unique_id",
        data={
            CONF_HOST: "192.168.0.123",
            CONF_ID: "00000000-0000-0000-0000-000000000000",
            CONF_NAME: "Tree 1",
            CONF_MODEL: TEST_MODEL,
        },
    )
    config_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        LIGHT_DOMAIN,
        DOMAIN,
        config_entry.unique_id,
    )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.unique_id)},
    )

    await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED

    assert entity_registry.async_get(entity_entry.entity_id).unique_id == TEST_MAC
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, config_entry.unique_id), config_entry.entry_id
    ).identifiers == {(DOMAIN, TEST_MAC)}
    assert config_entry.unique_id == TEST_MAC


@pytest.mark.usefixtures("mock_twinkly_client")
async def test_request_retried_once_on_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """A request that times out once is retried, so setup still succeeds."""
    details = await async_load_json_object_fixture(hass, "get_details.json", DOMAIN)
    # Only the first call times out; without the retry setup would fail here.
    mock_twinkly_client.get_details.side_effect = [TimeoutError, details, details]

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_request_gives_up_after_the_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """A request that keeps timing out still fails, after exactly one retry."""
    mock_twinkly_client.get_details.side_effect = TimeoutError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_twinkly_client.get_details.call_count == 2
