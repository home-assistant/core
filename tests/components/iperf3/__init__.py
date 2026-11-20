"""Tests for the iperf3 integration."""

from unittest.mock import MagicMock

from homeassistant.components.iperf3.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

HOST_1 = "192.168.1.10"
HOST_2 = "192.168.1.11"


def make_result() -> MagicMock:
    """Return a successful iperf3 test result."""
    return MagicMock(error=None, received_Mbps=200.0, sent_Mbps=100.0, version="3.20")


async def setup_iperf3(hass: HomeAssistant, hosts: list[str], manual: bool) -> None:
    """Set up the iperf3 integration for the given hosts."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"hosts": [{"host": host} for host in hosts], "manual": manual}},
    )
    await hass.async_block_till_done()
