"""Tests for the KACO RS485 integration."""

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.kaco_rs485.const import (
    CONF_ADDRESSES,
    CONF_INVERTERS,
    CONF_SW_VERSION,
)
from homeassistant.components.kaco_rs485.coordinator import SCAN_INTERVAL
from homeassistant.const import CONF_MODEL, CONF_PORT
from homeassistant.core import HomeAssistant

MOCK_PORT = "/dev/ttyUSB0"
MOCK_PORT_DESCRIPTION = "AtomS3 Lite RS485 (RS-485)"

# The library calls an inverter asleep after three consecutive misses.
CYCLES_UNTIL_DARK = 4

# 6400xi at 1 and 2, 8000xi at 4 — the layout the captured frames came from.
MOCK_ADDRESSES = [1, 2, 4]

MOCK_ENTRY_DATA = {
    CONF_PORT: MOCK_PORT,
    CONF_ADDRESSES: MOCK_ADDRESSES,
    CONF_INVERTERS: {
        "1": {CONF_MODEL: "6400xi", CONF_SW_VERSION: "K222.36DE 6817"},
        "2": {CONF_MODEL: "6400xi", CONF_SW_VERSION: "K222.36DE 6817"},
        "4": {CONF_MODEL: "8000xi", CONF_SW_VERSION: "K222.36DE 1C5F"},
    },
}


async def run_cycles(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, count: int
) -> None:
    """Let the coordinator poll `count` times."""
    for _ in range(count):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
