"""Tests for device-initiated outgoing connections."""

from unittest.mock import MagicMock

from aioesphomeapi import ZERO_NOISE_PSK, APIClient
import pytest

from homeassistant.components.esphome.const import CONF_NOISE_PSK, DOMAIN
from homeassistant.components.esphome.outgoing_connection import (
    async_register_outgoing_target,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CoreState, HomeAssistant

from . import VALID_NOISE_PSK
from .conftest import MockESPHomeDeviceType

from tests.common import MockConfigEntry

MAC = "11:22:33:44:55:aa"


def _make_entry(
    *,
    noise_psk: str | None = VALID_NOISE_PSK,
    unique_id: str = MAC,
) -> MockConfigEntry:
    data = {CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""}
    if noise_psk is not None:
        data[CONF_NOISE_PSK] = noise_psk
    return MockConfigEntry(domain=DOMAIN, data=data, unique_id=unique_id)


async def test_outgoing_connection_registration(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_outgoing_connection_server: MagicMock,
) -> None:
    """An encrypted entry registers with the shared listener."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    assert mock_outgoing_connection_server.register.call_args.args[0] == MAC
    # The client declares itself a dial-back target in its hello
    assert mock_client.outgoing_connection_target is True

    # Unloading the entry removes its route; the library owns the rest
    unregister = mock_outgoing_connection_server.register.return_value
    unregister.assert_not_called()
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    unregister.assert_called()


@pytest.mark.parametrize("noise_psk", [None, "", ZERO_NOISE_PSK])
async def test_outgoing_connection_requires_noise_psk(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_outgoing_connection_server: MagicMock,
    noise_psk: str | None,
) -> None:
    """No real key (missing, empty, or the zero provisioning PSK), no route."""
    entry = _make_entry(noise_psk=noise_psk)
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    mock_outgoing_connection_server.register.assert_not_called()
    assert mock_client.outgoing_connection_target is False


async def test_outgoing_connection_shared_listener(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_outgoing_connection_server: MagicMock,
) -> None:
    """Two entries share the one listener; each registers its own MAC."""
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

    assert mock_outgoing_connection_server.register.call_count == 2
    macs = [
        call.args[0] for call in mock_outgoing_connection_server.register.call_args_list
    ]
    assert macs == [MAC, "aa:bb:cc:dd:ee:01"]


async def test_outgoing_connection_requires_mac_unique_id(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_outgoing_connection_server: MagicMock,
) -> None:
    """A pre-2023 non-MAC unique id gets no route and declares no flag."""
    entry = _make_entry(unique_id="my-old-device")
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    mock_outgoing_connection_server.register.assert_not_called()
    assert mock_client.outgoing_connection_target is False


async def test_outgoing_connection_stops_on_hass_stop(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_outgoing_connection_server: MagicMock,
) -> None:
    """The shared listener is closed when Home Assistant stops."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_outgoing_connection_server.close.assert_called_once()


async def test_outgoing_connection_not_started_during_shutdown(
    hass: HomeAssistant,
    mock_outgoing_connection_server: MagicMock,
) -> None:
    """No route is registered once Home Assistant is stopping."""
    hass.set_state(CoreState.stopping)
    assert async_register_outgoing_target(hass, MAC, MagicMock()) is None
    mock_outgoing_connection_server.register.assert_not_called()


async def test_outgoing_connection_register_error_does_not_fail_setup(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_outgoing_connection_server: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A raising register is contained; the entry still loads."""
    mock_outgoing_connection_server.register.side_effect = RuntimeError("boom")
    entry = _make_entry()
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert "Could not set up dial-in routing" in caplog.text
