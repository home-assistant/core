"""Tests for the ccm15 component."""

from unittest.mock import AsyncMock

from ccm15 import CCM15DeviceState, CCM15SlaveDevice
import httpx
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("ccm15_device")
async def test_load_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the config entry loads and unloads."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_non_contiguous_slots(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    ccm15_device: AsyncMock,
) -> None:
    """Entities for sparse slot indices, including >= 32, are available.

    ``devices`` is keyed by the true slot index, which can be sparse and reach
    >= 32. The coordinator must look devices up by key, not assume a contiguous
    0..N-1 range, or any entity past a gap stays permanently unavailable.
    """
    ccm15_device.return_value = CCM15DeviceState(
        devices={
            4: CCM15SlaveDevice(bytes.fromhex("000000b0b8001b")),
            33: CCM15SlaveDevice(bytes.fromhex("00000041c0001a")),
        }
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    for entity_id in ("climate.midea_4", "climate.midea_33"):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != "unavailable"


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    ccm15_device: AsyncMock,
) -> None:
    """Setup is retried when the controller cannot be reached."""
    ccm15_device.side_effect = httpx.RequestError("Connection failed")
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
