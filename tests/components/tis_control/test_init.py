"""Test setting up and unloading TIS Control."""

import asyncio
from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry
from tis_smartbus import TISConnectionError

from homeassistant.components.tis_control.const import DOMAIN, MAX_PARALLEL_READS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PORT, STATE_ON
from homeassistant.core import HomeAssistant


async def test_setup_and_unload(
    hass: HomeAssistant, mock_gateway: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry loads and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_gateway.close.assert_awaited_once()


async def test_setup_retries_when_port_unavailable(
    hass: HomeAssistant, mock_gateway: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup is retried when the UDP port cannot be opened."""
    mock_gateway.connect.side_effect = TISConnectionError("port busy")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_when_first_read_fails(
    hass: HomeAssistant, mock_gateway: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A failure during the first read closes the connection and retries later."""
    mock_gateway.read_channels.side_effect = TISConnectionError("not connected")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_gateway.close.assert_awaited_once()


async def test_large_site_is_read_a_few_modules_at_a_time(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Thirty modules behind one gateway all stay available.

    The bus serves one frame at a time, so a gateway can only answer so many reads inside the read timeout.
    The fake below times out a read that starts with more than 25 others already waiting, which is where a
    real 9600-baud bus runs past 2 s. Reading every module at once lost the last five.
    """
    modules = [(2, device) for device in range(1, 31)]
    for address in modules:
        mock_gateway.levels[address] = [100]
    read = mock_gateway.read_channels.side_effect
    waiting = 0
    most_waiting = 0

    async def serial_bus(
        subnet: int, device: int, timeout: float = 2.0
    ) -> list[int] | None:
        nonlocal waiting, most_waiting
        waiting += 1
        most_waiting = max(most_waiting, waiting)
        too_late = waiting > 25
        try:
            for _ in range(3):  # let every other read that is allowed to start, start
                await asyncio.sleep(0)
            return None if too_late else await read(subnet, device, timeout)
        finally:
            waiting -= 1

    mock_gateway.read_channels.side_effect = serial_bus
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.1.60:6000",
        data={
            CONF_HOST: "192.168.1.60",
            CONF_PORT: 6000,
            CONF_DEVICES: [
                {
                    "subnet": s,
                    "device": d,
                    "channel": 1,
                    "module": f"Dimmer {d}",
                    "model": "DIM-6CH-2A",
                }
                for s, d in modules
            ],
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert most_waiting == MAX_PARALLEL_READS
    states = [hass.states.get(f"light.dimmer_{d}_channel_1") for _, d in modules]
    assert [state.state if state else None for state in states] == [STATE_ON] * 30
