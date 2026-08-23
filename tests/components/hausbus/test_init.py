"""Tests for the hausbus __init__.py setup/unload lifecycle."""

from unittest.mock import MagicMock

from homeassistant.components.hausbus.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload_listener_symmetry(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """Setup should register both listener types; unload should remove both.

    HausbusGateway.__init__ calls both addBusEventListener(self) and
    addBusDeviceListener(self) on the pyhausbus HomeServer singleton.
    async_unload_entry must symmetrically remove both, otherwise the
    (now-unloaded) gateway instance would stay registered as a device
    listener forever - a real leak given HomeServer is a process-wide
    singleton whose side effects persist across config entry reload cycles.
    """
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    gateway = entry.runtime_data
    # HomeServer() is patched separately for gateway.py by the fixture,
    # so gateway.home_server is its own MagicMock instance.
    gateway.home_server.addBusEventListener.assert_called_once_with(gateway)
    gateway.home_server.addBusDeviceListener.assert_called_once_with(gateway)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    gateway.home_server.removeBusEventListener.assert_called_once_with(gateway)
    gateway.home_server.removeBusDeviceListener.assert_called_once_with(gateway)
