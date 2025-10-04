"""Test the Portainer initial specific behavior."""

from unittest.mock import AsyncMock

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
import pytest

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


async def test_device_migration(hass: HomeAssistant) -> None:
    """Test migration of device identifiers from v3 to v4."""

    # Create a mock config entry at version 3
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "http://test_host",
            CONF_API_TOKEN: "test_key",
            CONF_VERIFY_SSL: True,
        },
        unique_id="1",
        version=3,
    )
    entry.add_to_hass(hass)

    # Create device registry entries to simulate old format
    device_registry = dr.async_get(hass)

    # Create endpoint device
    endpoint_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_endpoint1")},
        name="Test Endpoint",
        model="Endpoint",
    )

    # Create container device with old format identifier
    container_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_test_container")},
        name="Test Container",
        model="Container",
    )

    # Manually set via_device_id to simulate the relationship
    device_registry.async_update_device(
        container_device.id, via_device_id=endpoint_device.id
    )
    container_device = device_registry.async_get(container_device.id)

    # Verify old format
    assert container_device.identifiers == {
        (DOMAIN, f"{entry.entry_id}_test_container")
    }
    assert container_device.via_device_id == endpoint_device.id

    # Run migration by setting up the entry
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration occurred
    assert entry.version == 4

    # Check that device identifier was updated
    updated_device = device_registry.async_get(container_device.id)
    expected_identifier = f"{entry.entry_id}_endpoint1_test_container"
    assert updated_device.identifiers == {(DOMAIN, expected_identifier)}


async def test_device_migration_fallback(hass: HomeAssistant) -> None:
    """Test migration fallback when via_device relationship is broken."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "http://test_host",
            CONF_API_TOKEN: "test_key",
            CONF_VERIFY_SSL: True,
        },
        unique_id="1",
        version=3,
    )
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)

    # Create container without via_device_id (fallback case)
    container_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_orphaned_container")},
        name="Orphaned Container",
        model="Container",
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Should keep old format since no via_device (fallback)
    updated_device = device_registry.async_get(container_device.id)
    assert updated_device.identifiers == {
        (DOMAIN, f"{entry.entry_id}_orphaned_container")
    }
