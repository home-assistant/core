"""Tests for the LibreSync integration setup."""

import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

from aiolibresync import LssdpInfo, NotConnectedError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.libresync.const import CONNECT_TIMEOUT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import HOST, LS9, STATE, push


async def test_load_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Test the entry connects on setup and disconnects on unload."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.async_connect.assert_awaited_once_with(timeout=CONNECT_TIMEOUT)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_client.async_disconnect.assert_awaited_once()


@pytest.mark.parametrize("lssdp", [LS9, None], ids=["ls9", "no_lssdp"])
async def test_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_lssdp: AsyncMock,
    lssdp: LssdpInfo | None,
) -> None:
    """Test a hub that does not answer in time is retried."""
    mock_lssdp.return_value = lssdp
    mock_client.async_connect.side_effect = NotConnectedError("no answer")
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.reason == (
        f"The hub at {HOST} did not answer on ports 50006 and 7777"
    )
    assert mock_client.subscribers == []


@pytest.mark.parametrize(
    "connect_error", [NotConnectedError("no answer"), None], ids=["fails", "connects"]
)
async def test_unsupported_hub_not_retried(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_lssdp: AsyncMock,
    connect_error: Exception | None,
) -> None:
    """Test an entry on an LS10 hub fails setup instead of retrying for ever."""
    mock_lssdp.return_value = replace(LS9, module="LS10")
    mock_client.async_connect.side_effect = connect_error
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_client.async_disconnect.assert_awaited_once()
    assert mock_config_entry.reason == (
        f"The hub at {HOST} is built on Libre's newer LS10 module, which this "
        "integration does not support yet"
    )
    mock_lssdp.assert_awaited_once_with(HOST)


async def test_device_updated(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the model reaches the device when it arrives, and the serial never."""
    mock_client.state = STATE.evolve(serial=None, model=None)
    await setup_integration(hass, mock_config_entry)

    push(mock_client, STATE)
    await hass.async_block_till_done()
    [device] = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device.model == "Stereo Hub"
    assert device.serial_number is None


async def test_device_keeps_identity_across_reload(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test a reload before the model is answered keeps it."""
    await setup_integration(hass, mock_config_entry)
    [device] = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device.model == "Stereo Hub"

    mock_client.state = STATE.evolve(serial=None, model=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    [device] = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device.model == "Stereo Hub"


async def test_lssdp_error_propagates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_lssdp: AsyncMock,
) -> None:
    """Test an unexpected LSSDP error disconnects the client and fails setup."""
    mock_lssdp.side_effect = RuntimeError("boom")
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_client.async_disconnect.assert_awaited_once()


async def test_connect_error_propagates(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Test an unexpected connect error fails setup."""
    mock_client.async_connect.side_effect = RuntimeError("boom")
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_cancelled_setup_disconnects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_lssdp: AsyncMock,
) -> None:
    """Test a setup cancelled after the connection opened disconnects it."""
    pending = asyncio.Event()

    async def never_answers(host: str) -> None:
        pending.set()
        await asyncio.Event().wait()

    mock_lssdp.side_effect = never_answers
    mock_config_entry.add_to_hass(hass)
    setup = hass.async_create_task(
        hass.config_entries.async_setup(mock_config_entry.entry_id)
    )
    await pending.wait()
    mock_client.async_connect.assert_awaited_once()
    setup.cancel()
    with pytest.raises(asyncio.CancelledError):
        await setup
    mock_client.async_disconnect.assert_awaited_once()
