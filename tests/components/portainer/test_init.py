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
from homeassistant.helpers import device_registry as dr, entity_registry as er

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

    assert CONF_HOST not in entry.data
    assert CONF_API_KEY not in entry.data
    assert entry.data[CONF_URL] == "http://test_host"
    assert entry.data[CONF_API_TOKEN] == "test_key"
    assert entry.data[CONF_VERIFY_SSL] is True

    # Confirm we went through all current migrations
    assert entry.version == 4


async def test_migration_v3_to_v4(hass: HomeAssistant) -> None:
    """Test migration from v3 config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://test_host",
            CONF_API_KEY: "test_key",
        },
        unique_id="1",
        version=3,
    )
    entry.add_to_hass(hass)
    assert entry.version == 3

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    endpoint_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_endpoint_1")},
        name="Test Endpoint",
    )

    original_container_identifier = f"{entry.entry_id}_adguard"
    container_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, original_container_identifier)},
        via_device=(DOMAIN, f"{entry.entry_id}_endpoint_1"),
        name="Test Container",
    )

    container_entity = entity_registry.async_get_or_create(
        domain="switch",
        platform=DOMAIN,
        unique_id=f"{entry.entry_id}_adguard_container",
        config_entry=entry,
        device_id=container_device.id,
        original_name="Test Container Switch",
    )

    assert container_device.via_device_id == endpoint_device.id
    assert container_device.identifiers == {(DOMAIN, original_container_identifier)}
    assert container_entity.unique_id == f"{entry.entry_id}_adguard_container"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 4

    # Fetch again, to assert the new identifiers
    container_after = device_registry.async_get(container_device.id)
    entity_after = entity_registry.async_get(container_entity.entity_id)

    assert container_after.identifiers == {(DOMAIN, f"{entry.entry_id}_1_adguard")}
    assert entity_after.unique_id == f"{entry.entry_id}_1_adguard_container"
