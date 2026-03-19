"""Tests for the wiim integration."""

from unittest.mock import MagicMock

from wiim.consts import PlayingStatus

from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the component."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://192.168.1.10:8123"},
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def fire_general_update(hass: HomeAssistant, mock_device: MagicMock) -> None:
    """Trigger the registered general update callback on the mock device."""
    assert mock_device.general_event_callback is not None
    mock_device.general_event_callback(mock_device)
    await hass.async_block_till_done()


async def fire_transport_update(
    hass: HomeAssistant,
    mock_device: MagicMock,
    transport_state: PlayingStatus,
) -> None:
    """Trigger the registered AVTransport callback on the mock device."""
    assert mock_device.av_transport_event_callback is not None
    mock_device.event_data = {"TransportState": transport_state.value}
    mock_device.av_transport_event_callback(MagicMock(), [])
    await hass.async_block_till_done()
