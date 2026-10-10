"""Tests for the Hunter Douglas PowerView integration setup and device removal."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hunterdouglas_powerview import (
    async_remove_config_entry_device,
)
from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .const import MOCK_MAC, MOCK_SERIAL

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


def _get_hub_device(
    device_registry: dr.DeviceRegistry, entry: MockConfigEntry
) -> dr.DeviceEntry:
    """Return the hub device (the only one with no parent) for an entry."""
    return next(
        device
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        if device.via_device_id is None
    )


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_not_primary_hub(hass: HomeAssistant) -> None:
    """Test setup fails when the hub is not the primary hub."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    hub = MagicMock(hub_address="1.2.3.4", role="Secondary")
    hub.name = "PowerView Hub"

    with patch(
        "homeassistant.components.hunterdouglas_powerview.async_connect_hub",
        AsyncMock(return_value=MagicMock(hub=hub)),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == (
        "PowerView Hub (1.2.3.4) is performing role of Secondary Hub. Only the"
        " Primary Hub can manage shades"
    )


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_remove_phantom_shade_via_websocket(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a shade the hub no longer reports can be deleted from the UI."""
    assert await async_setup_component(hass, "config", {})
    entry = await _setup_entry(hass)
    phantom = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "99999")},
        via_device_id=hub.id,
    )

    client = await hass_ws_client(hass)
    response = await client.remove_device(phantom.id, entry.entry_id)

    assert response["success"]
    assert device_registry.async_get(phantom.id) is None


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_remove_active_shade_and_hub_blocked(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test the hub and shades still on the hub cannot be removed."""
    entry = await _setup_entry(hass)
    hub = device_registry.async_get_device(identifiers={(DOMAIN, MOCK_SERIAL)})
    assert hub is not None
    shade = next(
        device
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        if device.via_device_id
    )

    assert not await async_remove_config_entry_device(hass, entry, hub)
    assert not await async_remove_config_entry_device(hass, entry, shade)


async def test_remove_device_blocked_when_entry_not_loaded(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test removal is refused (not an error) when the entry has no runtime data."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, MOCK_SERIAL)}
    )
    shade = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "99999")},
        via_device_id=hub.id,
    )

    assert not await async_remove_config_entry_device(hass, entry, shade)
