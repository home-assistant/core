"""Tests for the Hinen integration init module."""

import time
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.hinen import delete_devices
from homeassistant.components.hinen.const import AUTH, COORDINATOR, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MockHinen
from .conftest import TOKEN_URL, ComponentSetup

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_async_setup_entry_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test successful setup of the integration."""
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.hinen.HinenDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.hinen.AsyncConfigEntryAuth.check_and_refresh_token",
            return_value=None,
        ),
        patch(
            "homeassistant.components.hinen.delete_devices",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert result
    assert config_entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert config_entry.entry_id in hass.data[DOMAIN]
    assert COORDINATOR in hass.data[DOMAIN][config_entry.entry_id]
    assert AUTH in hass.data[DOMAIN][config_entry.entry_id]

    assert hasattr(config_entry, "runtime_data")
    assert config_entry.runtime_data is not None


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test expired token is refreshed."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        TOKEN_URL,
        json={
            "data": {
                "access_token": "updated-access-token",
                "refresh_token": "updated-refresh-token",
                "expires_at": time.time() + 3600,
                "expires_in": 3600,
            }
        },
    )

    service = MockHinen(hass)
    with patch(
        "homeassistant.components.hinen.AsyncConfigEntryAuth.get_resource",
        return_value=service,
    ):
        await setup_integration()

        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        assert entries[0].state is ConfigEntryState.LOADED
        assert entries[0].data["token"]["access_token"] == "updated-access-token"
        assert entries[0].data["token"]["expires_in"] == 3600


async def test_async_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test successful unload of the integration."""
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.hinen.HinenDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.hinen.AsyncConfigEntryAuth.check_and_refresh_token",
            return_value=None,
        ),
        patch(
            "homeassistant.components.hinen.delete_devices",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_delete_devices(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test delete_devices function."""
    config_entry.add_to_hass(hass)
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"device_1": {}, "device_2": {}}

    device_registry = dr.async_get(hass)
    device1 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "device_1")},
        manufacturer="Hinen",
        name="Test Device 1",
    )
    device2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "device_3")},  # Different device ID
        manufacturer="Hinen",
        name="Test Device 2",
    )

    with patch(
        "homeassistant.components.hinen.dr.async_get", return_value=device_registry
    ):
        await delete_devices(hass, config_entry, mock_coordinator)

    updated_device1 = device_registry.async_get(device1.id)
    updated_device2 = device_registry.async_get(device2.id)
    assert updated_device1 is None
    assert updated_device2 is not None
    assert config_entry.entry_id in updated_device2.config_entries


async def test_delete_devices_empty_coordinator_data(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test delete_devices function with empty coordinator data."""
    config_entry.add_to_hass(hass)
    mock_coordinator = MagicMock()
    mock_coordinator.data = {}
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "device_1")},
        manufacturer="Hinen",
        name="Test Device",
    )
    with patch(
        "homeassistant.components.hinen.dr.async_get", return_value=device_registry
    ):
        await delete_devices(hass, config_entry, mock_coordinator)

    updated_device = device_registry.async_get(device.id)
    assert updated_device is not None
    assert config_entry.entry_id in updated_device.config_entries
