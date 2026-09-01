"""Tests for device-initiated outgoing connections."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aioesphomeapi import ZERO_NOISE_PSK, APIClient
import pytest

from homeassistant.components.esphome.const import CONF_NOISE_PSK, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDeviceType

from tests.common import MockConfigEntry

MAC = "11:22:33:44:55:aa"


def _make_entry(
    *,
    noise_psk: str | None = "bOFFzzvfpg5DB94DuBGLXD/hMnhpDKgP9UQyBulwWVU=",
    unique_id: str = MAC,
) -> MockConfigEntry:
    data = {CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""}
    if noise_psk is not None:
        data[CONF_NOISE_PSK] = noise_psk
    return MockConfigEntry(domain=DOMAIN, data=data, unique_id=unique_id)


@pytest.fixture
def mock_server() -> Generator[MagicMock]:
    """Patch the aioesphomeapi listener class in the singleton module."""
    server = MagicMock()
    server.start = AsyncMock()
    server.stop = AsyncMock()
    server.register = MagicMock(return_value=MagicMock())
    with patch(
        "homeassistant.components.esphome.outgoing_connection.OutgoingConnectionServer",
        return_value=server,
    ):
        yield server


async def test_outgoing_connection_registration(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
) -> None:
    """An encrypted entry always registers with the shared listener."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    assert mock_server.register.call_args.args[0] == MAC
    # The client declares itself a dial-back target in its hello
    assert mock_client.outgoing_connection_target is True

    unregister = mock_server.register.return_value
    unregister.assert_not_called()
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    unregister.assert_called()
    # The last unregistration stops the listener and frees the port
    mock_server.stop.assert_awaited_once()


@pytest.mark.parametrize("noise_psk", [None, ""])
async def test_outgoing_connection_requires_noise_psk(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
    noise_psk: str | None,
) -> None:
    """A keyless entry (missing or empty key) never registers or sets the flag."""
    entry = _make_entry(noise_psk=noise_psk)
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    mock_server.register.assert_not_called()
    assert mock_client.outgoing_connection_target is False


async def test_outgoing_connection_listener_unavailable(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
) -> None:
    """Setup continues when the listener port cannot be bound."""
    mock_server.start.side_effect = OSError("address in use")
    entry = _make_entry()
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_server.register.assert_not_called()

    # The failure is not cached; a reload retries the bind
    mock_server.start.side_effect = None
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    mock_server.register.assert_called_once()


async def test_outgoing_connection_shared_listener(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
) -> None:
    """Two entries share one listener; each registers its own MAC."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    entry2 = _make_entry(unique_id="aa:bb:cc:dd:ee:01")
    entry2.add_to_hass(hass)
    await mock_esphome_device(
        mock_client=mock_client,
        entry=entry2,
        device_info={"mac_address": "AA:BB:CC:DD:EE:01", "name": "test2"},
    )
    await hass.async_block_till_done()

    mock_server.start.assert_awaited_once()
    assert mock_server.register.call_count == 2

    # Unloading one entry keeps the shared listener running
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    mock_server.stop.assert_not_awaited()
    await hass.config_entries.async_unload(entry2.entry_id)
    await hass.async_block_till_done()
    mock_server.stop.assert_awaited_once()


async def test_outgoing_connection_zero_psk_never_registers(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
) -> None:
    """The zero-PSK provisioning key authenticates nobody and never routes."""
    entry = _make_entry(noise_psk=ZERO_NOISE_PSK)
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    mock_server.register.assert_not_called()
    assert mock_client.outgoing_connection_target is False


async def test_outgoing_connection_requires_mac_unique_id(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
) -> None:
    """A pre-2023 non-MAC unique id has no route; the flag is still declared."""
    entry = _make_entry(unique_id="my-old-device")
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    mock_server.register.assert_not_called()
    assert mock_client.outgoing_connection_target is True
