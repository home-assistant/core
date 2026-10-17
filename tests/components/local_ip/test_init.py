"""Tests for the local_ip component."""

from unittest.mock import patch

import ifaddr
import pytest

from homeassistant.components.local_ip.const import DOMAIN
from homeassistant.components.network import MDNS_TARGET_IP, async_get_source_ip
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "address",
    [
        pytest.param("fd12:3456::10", id="unique_local"),
        pytest.param("2001:4860::10", id="global"),
    ],
)
async def test_ipv6_only(hass: HomeAssistant, address: str) -> None:
    """Use an enabled IPv6 address when there is no IPv4 interface."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.network.util.ifaddr.get_adapters",
            return_value=[
                ifaddr.Adapter(
                    "eth0", "eth0", [ifaddr.IP((address, 0, 0), 64, "eth0")], index=2
                )
            ],
        ),
        patch(
            "homeassistant.components.network.util.async_get_source_ip",
            side_effect={"127.0.0.1": "127.0.0.1"}.get,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"sensor.{DOMAIN}")
    assert state is not None
    assert state.state == address

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_basic_setup(hass: HomeAssistant) -> None:
    """Test component setup creates entry from config."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    local_ip = await async_get_source_ip(hass, target_ip=MDNS_TARGET_IP)
    state = hass.states.get(f"sensor.{DOMAIN}")
    assert state
    assert state.state == local_ip

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
