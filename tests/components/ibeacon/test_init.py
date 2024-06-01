"""Test the ibeacon init."""

import pytest

from homeassistant.components.ibeacon.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import BLUECHARM_BEACON_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


async def test_device_remove_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can only remove a device that no longer exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, "config", {})

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    inject_bluetooth_service_info(hass, BLUECHARM_BEACON_SERVICE_INFO)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={
            (
                DOMAIN,
                "426c7565-4368-6172-6d42-6561636f6e73_3838_4949_61DE521B-F0BF-9F44-64D4-75BBE1738105",
            )
        },
    )
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, entry.entry_id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "not_seen")},
    )
    response = await client.remove_device(dead_device_entry.id, entry.entry_id)
    assert response["success"]
