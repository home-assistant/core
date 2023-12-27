"""Tests for the Nibe Heat Pump integration."""

from typing import Any
from unittest.mock import AsyncMock

from nibe.coil import Coil, CoilData
from nibe.connection import Connection
from nibe.exceptions import ReadException
from nibe.heatpump import HeatPump, Model

from homeassistant.components.nibe_heatpump import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_ENTRY_DATA = {
    "model": None,
    "ip_address": "127.0.0.1",
    "listening_port": 9999,
    "remote_read_port": 10000,
    "remote_write_port": 10001,
    "word_swap": True,
    "connection_type": "nibegw",
}


class MockConnection(Connection):
    """A mock connection class."""

    def __init__(self) -> None:
        """Initialize the mock connection."""
        self.coils: dict[int, Any] = {}
        self.heatpump: HeatPump
        self.start = AsyncMock()
        self.stop = AsyncMock()
        self.write_coil = AsyncMock()
        self.verify_connectivity = AsyncMock()
        self.read_product_info = AsyncMock()

    async def read_coil(self, coil: Coil, timeout: float = 0) -> CoilData:
        """Read of coils."""
        if (data := self.coils.get(coil.address, None)) is None:
            raise ReadException()
        return CoilData(coil, data)

    async def write_coil(self, coil_data: CoilData, timeout: float = 10.0) -> None:
        """Write a coil data to the heatpump."""

    async def verify_connectivity(self):
        """Verify that we have functioning communication."""

    def mock_coil_update(self, coil_id: int, value: int | float | str | None):
        """Trigger an out of band coil update."""
        coil = self.heatpump.get_coil_by_address(coil_id)
        self.coils[coil_id] = value
        self.heatpump.notify_coil_update(CoilData(coil, value))


async def async_add_entry(hass: HomeAssistant, data: dict[str, Any]) -> MockConfigEntry:
    """Add entry and get the coordinator."""
    entry = MockConfigEntry(domain=DOMAIN, title="Dummy", data=data)

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    return entry


async def async_add_model(hass: HomeAssistant, model: Model) -> MockConfigEntry:
    """Add entry of specific model."""
    return await async_add_entry(hass, {**MOCK_ENTRY_DATA, "model": model.name})
