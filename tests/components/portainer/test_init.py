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
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


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

    assert entry.version == 3
    assert CONF_HOST not in entry.data
    assert CONF_API_KEY not in entry.data
    assert entry.data[CONF_URL] == "http://test_host"
    assert entry.data[CONF_API_TOKEN] == "test_key"
    assert entry.data[CONF_VERIFY_SSL] is True


@pytest.mark.parametrize(
    ("container_id", "expected_result"),
    [("1", False), ("5", True)],
    ids=("Present container", "Stale container"),
)
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    container_id: str,
    expected_result: bool,
) -> None:
    """Test manually removing an stale device."""
    assert await async_setup_component(hass, "config", {})
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_{container_id}")},
    )

    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(
        device_entry.id, mock_config_entry.entry_id
    )
    assert response["success"] == expected_result
