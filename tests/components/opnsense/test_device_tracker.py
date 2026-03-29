"""The tests for the opnsense device tracker platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.opnsense.const import (
    CONF_API_SECRET,
    CONF_TRACKER_INTERFACES,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

ARP_RESPONSE = [
    {
        "hostname": "",
        "intf": "igb1",
        "intf_description": "LAN",
        "ip": "192.168.0.123",
        "mac": "ff:ff:ff:ff:ff:ff",
        "manufacturer": "",
    },
    {
        "hostname": "Desktop",
        "intf": "igb1",
        "intf_description": "LAN",
        "ip": "192.168.0.167",
        "mac": "ff:ff:ff:ff:ff:fe",
        "manufacturer": "OEM",
    },
]


async def test_setup_entry_creates_device_entities(
    hass: HomeAssistant, mock_opnsense_client: AsyncMock
) -> None:
    """Test that setting up a config entry creates device tracker entities."""
    mock_opnsense_client.get_arp = AsyncMock(return_value=ARP_RESPONSE)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "https://fake_host_fun/api",
            CONF_API_KEY: "fake_key",
            CONF_API_SECRET: "fake_secret",
            CONF_VERIFY_SSL: False,
            CONF_TRACKER_INTERFACES: "",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == 2

    device_1 = hass.states.get("device_tracker.ff_ff_ff_ff_ff_ff")
    assert device_1 is not None
    assert device_1.state == STATE_HOME

    device_2 = hass.states.get("device_tracker.desktop")
    assert device_2 is not None
    assert device_2.state == STATE_HOME


async def test_setup_entry_filters_by_interface(
    hass: HomeAssistant, mock_opnsense_client: AsyncMock
) -> None:
    """Test that tracker interfaces filter ARP results."""
    arp_mixed = [
        *ARP_RESPONSE,
        {
            "hostname": "WanDevice",
            "intf": "igb0",
            "intf_description": "WAN",
            "ip": "10.0.0.1",
            "mac": "aa:bb:cc:dd:ee:ff",
            "manufacturer": "Test",
        },
    ]
    mock_opnsense_client.get_arp = AsyncMock(return_value=arp_mixed)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "https://fake_host_fun/api",
            CONF_API_KEY: "fake_key",
            CONF_API_SECRET: "fake_secret",
            CONF_VERIFY_SSL: False,
            CONF_TRACKER_INTERFACES: "WAN",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == 1

    device = hass.states.get("device_tracker.wandevice")
    assert device is not None
    assert device.state == STATE_HOME
