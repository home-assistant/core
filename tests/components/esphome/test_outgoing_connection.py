"""Tests for device-initiated outgoing connections."""

import logging
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


@pytest.fixture
def mock_server(mock_outgoing_connection_server: MagicMock) -> MagicMock:
    """The autouse listener mock from conftest, under its local name."""
    return mock_outgoing_connection_server


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
    mock_server.close.assert_called_once()


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

    mock_server.start.assert_called_once()
    assert mock_server.register.call_count == 2

    # Unloading one entry keeps the shared listener running
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    mock_server.close.assert_not_called()
    await hass.config_entries.async_unload(entry2.entry_id)
    await hass.async_block_till_done()
    mock_server.close.assert_called_once()


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
    """A pre-2023 non-MAC unique id gets no route and declares no flag."""
    entry = _make_entry(unique_id="my-old-device")
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    mock_server.register.assert_not_called()
    assert mock_client.outgoing_connection_target is False


async def test_outgoing_connection_listener_restarts_after_last_unload(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
) -> None:
    """A new entry after the last unload rebinds the listener."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    mock_server.close.assert_called_once()

    entry2 = _make_entry(unique_id="aa:bb:cc:dd:ee:01")
    entry2.add_to_hass(hass)
    await mock_esphome_device(
        mock_client=mock_client,
        entry=entry2,
        device_info={"mac_address": "AA:BB:CC:DD:EE:01", "name": "test2"},
    )
    await hass.async_block_till_done()
    assert mock_server.start.call_count == 2
    assert mock_server.register.call_count == 2


async def test_outgoing_connection_stops_on_hass_stop(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
) -> None:
    """The shared listener is stopped when Home Assistant stops."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_server.close.assert_called_once()


async def test_outgoing_connection_bind_failure_warns_once(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """N devices behind a taken port produce one warning, not N."""
    mock_server.start.side_effect = OSError("address in use")
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

    mock_server.register.assert_not_called()
    warnings = [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING
        and "Cannot listen for ESPHome outgoing connections" in record.message
    ]
    assert len(warnings) == 1


async def test_outgoing_connection_rebind_after_close(
    hass: HomeAssistant,
    mock_server: MagicMock,
) -> None:
    """close() is synchronous, so the next registration rebinds directly."""
    unregister = async_register_outgoing_target(hass, MAC, MagicMock())
    assert unregister is not None
    unregister()
    mock_server.close.assert_called_once()
    assert (
        async_register_outgoing_target(hass, "aa:bb:cc:dd:ee:01", MagicMock())
        is not None
    )
    assert mock_server.start.call_count == 2


async def test_outgoing_connection_not_started_during_shutdown(
    hass: HomeAssistant,
    mock_server: MagicMock,
) -> None:
    """No listener is started once Home Assistant is stopping."""
    hass.set_state(CoreState.stopping)
    assert async_register_outgoing_target(hass, MAC, MagicMock()) is None
    mock_server.start.assert_not_called()


async def test_outgoing_connection_unregister_error_contained(
    hass: HomeAssistant,
    mock_server: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A raising library unregister recovers by discarding just that route."""
    mock_server.register.return_value = MagicMock(side_effect=RuntimeError("boom"))
    unregister = async_register_outgoing_target(hass, MAC, MagicMock())
    assert unregister is not None
    unregister()
    assert "Error removing the dial-in route" in caplog.text
    mock_server.discard.assert_called_once_with(MAC)
    # The last registration is gone, so the listener stops on the normal path
    mock_server.close.assert_called_once()


async def test_outgoing_connection_register_error_stops_listener(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_server: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A raising register tears the fresh listener down; setup still loads."""
    mock_server.register.side_effect = RuntimeError("boom")
    entry = _make_entry()
    entry.add_to_hass(hass)
    await mock_esphome_device(mock_client=mock_client, entry=entry, device_info={})
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert "Could not set up dial-in routing" in caplog.text
    mock_server.close.assert_called_once()


async def test_outgoing_connection_unregister_error_spares_survivors(
    hass: HomeAssistant,
    mock_server: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One entry's failed unregister does not unroute the other entries."""
    bad_unregister = MagicMock(side_effect=RuntimeError("boom"))
    good_unregister = MagicMock()
    mock_server.register.side_effect = [bad_unregister, good_unregister]
    first = async_register_outgoing_target(hass, MAC, MagicMock())
    second = async_register_outgoing_target(hass, "aa:bb:cc:dd:ee:01", MagicMock())
    assert first is not None
    assert second is not None

    first()
    assert "Error removing the dial-in route" in caplog.text
    mock_server.discard.assert_called_once_with(MAC)
    # The shared listener survives for the remaining registration
    mock_server.close.assert_not_called()

    second()
    mock_server.close.assert_called_once()


async def test_outgoing_connection_discard_failure_stops_shared_listener(
    hass: HomeAssistant,
    mock_server: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When even discard fails the routes are unknowable; all is torn down."""
    bad_unregister = MagicMock(side_effect=RuntimeError("boom"))
    good_unregister = MagicMock()
    mock_server.register.side_effect = [bad_unregister, good_unregister]
    mock_server.discard.side_effect = RuntimeError("boom2")
    first = async_register_outgoing_target(hass, MAC, MagicMock())
    second = async_register_outgoing_target(hass, "aa:bb:cc:dd:ee:01", MagicMock())
    assert first is not None
    assert second is not None

    first()
    assert "Error discarding the dial-in route" in caplog.text
    assert "1 other device(s) will not receive dial-ins" in caplog.text
    mock_server.close.assert_called_once()
    # The survivor's unregister is a no-op against the gone listener
    second()
    mock_server.close.assert_called_once()


async def test_outgoing_connection_close_error_contained(
    hass: HomeAssistant,
    mock_server: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A raising close() cannot abort the remaining cleanup."""
    mock_server.close.side_effect = RuntimeError("boom")
    unregister = async_register_outgoing_target(hass, MAC, MagicMock())
    assert unregister is not None
    unregister()
    assert "Error closing the outgoing connection listener" in caplog.text
    # The manager forgot the listener despite the failed close
    assert async_register_outgoing_target(hass, MAC, MagicMock()) is not None
    assert mock_server.start.call_count == 2
