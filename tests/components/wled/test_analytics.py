"""Tests for analytics platform."""

import pytest

from homeassistant.components.analytics import async_devices_payload
from homeassistant.components.wled import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_analytics(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test the analytics platform."""
    await async_setup_component(hass, "analytics", {})

    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={(DOMAIN, "test")},
        manufacturer="Test Manufacturer",
    )

    result = await async_devices_payload(hass)
    assert DOMAIN not in result["integrations"]
