"""Test the Portainer initial specific behavior."""

from unittest.mock import AsyncMock

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
import pytest

from homeassistant.components.portainer import async_migrate_entry
from homeassistant.components.portainer.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (PortainerAuthenticationError("bad creds"), ConfigEntryState.SETUP_ERROR),
        (PortainerConnectionError("cannot connect"), ConfigEntryState.SETUP_RETRY),
        (PortainerTimeoutError("timeout"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test the _async_setup."""
    mock_portainer_client.get_endpoints.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state == expected_state


async def test_migrations(hass: HomeAssistant) -> None:
    """Test migration from v1 config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://test_host",
            CONF_API_KEY: "test_key",
        },
        unique_id="1",
        version=1,
    )
    entry.add_to_hass(hass)
    assert entry.version == 1
    assert CONF_VERIFY_SSL not in entry.data
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 4
    assert CONF_HOST not in entry.data
    assert CONF_API_KEY not in entry.data
    assert entry.data[CONF_URL] == "http://test_host"
    assert entry.data[CONF_API_TOKEN] == "test_key"
    assert entry.data[CONF_VERIFY_SSL] is True


async def test_device_migration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test migration of device identifiers from v3 to v4."""
    mock_config_entry.version = 3
    mock_config_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)

    endpoint_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_endpoint1")},
        name="Test Endpoint",
        model="Endpoint",
    )

    container_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_test_container")},
        name="Test Container",
        model="Container",
        via_device_id=endpoint_device.id,
    )

    assert container_device.identifiers == {
        (DOMAIN, f"{mock_config_entry.entry_id}_test_container")
    }

    assert await async_migrate_entry(hass, mock_config_entry)
    assert mock_config_entry.version == 4

    updated_device = device_registry.async_get(container_device.id)
    expected_identifier = f"{mock_config_entry.entry_id}_endpoint1_test_container"
    assert updated_device.identifiers == {(DOMAIN, expected_identifier)}


async def test_device_migration_skips_endpoints(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test migration skips endpoint devices (those without via_device_id)."""
    mock_config_entry.version = 3
    mock_config_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)

    endpoint_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_endpoint1")},
        name="Test Endpoint",
        model="Endpoint",
    )

    assert await async_migrate_entry(hass, mock_config_entry)

    updated_device = device_registry.async_get(endpoint_device.id)
    assert updated_device.identifiers == {
        (DOMAIN, f"{mock_config_entry.entry_id}_endpoint1")
    }
