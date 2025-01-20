"""Test diagnostics for Home Connect."""

from collections.abc import Awaitable, Callable
import re
from unittest.mock import AsyncMock, MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.components.home_connect.diagnostics import (
    HomeConnectError,
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

HA_ID_REGEX = re.compile(r"/homeappliances/(?P<ha_id>[^/]+)/programs/available")


def set_side_effect_to_client(client: MagicMock) -> None:
    """Set side effect to client auth request to obtaint the programs."""

    async def side_effect(*args, **kwargs):
        ha_id = HA_ID_REGEX.match(args[1]).group("ha_id")
        response = MagicMock()
        response.json.return_value = {
            "data": (await client.get_available_programs(ha_id)).to_dict()
        }
        response.is_error = False
        return response

    client._auth.request.side_effect = side_effect


async def test_async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    set_side_effect_to_client(client)
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    assert await async_get_config_entry_diagnostics(hass, config_entry) == snapshot


async def test_async_get_device_diagnostics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device config entry diagnostics."""
    set_side_effect_to_client(client)
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "SIEMENS-HCS02DWH1-6BE58C26DCC1")},
    )

    assert await async_get_device_diagnostics(hass, config_entry, device) == snapshot


@pytest.mark.parametrize(
    "request_side_effect",
    [
        AsyncMock(side_effect=HomeConnectError()),
        AsyncMock(is_error=True),
    ],
)
async def test_async_device_diagnostics_api_error(
    request_side_effect: AsyncMock,
    appliance_ha_id: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that the device diagnostics are generated even if an API error occurs."""
    client_with_exception._auth.request = request_side_effect
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client_with_exception)
    assert config_entry.state == ConfigEntryState.LOADED

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, appliance_ha_id)},
    )

    diagnostics = await async_get_device_diagnostics(hass, config_entry, device)
    assert diagnostics["programs"] is None
