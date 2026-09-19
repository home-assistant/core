"""Tests for the EARN-E P1 Meter integration setup."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntries, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import (
    CONF_SERIAL,
    DOMAIN,
    MOCK_HOST_2,
    MOCK_MAC,
    MOCK_SERIAL,
    MOCK_SERIAL_2,
    trigger_callback,
)

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test successful setup of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_listener.start.assert_awaited_once()
    mock_listener.register.assert_called_once()


async def test_setup_entry_oserror_raises_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test that OSError during setup raises ConfigEntryNotReady."""
    mock_listener.start = AsyncMock(side_effect=OSError("Address in use"))

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test unloading a config entry stops the shared listener."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_listener.unregister.assert_called()
    mock_listener.stop.assert_awaited()


async def test_unload_entry_keeps_listener_for_remaining_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_entry_2: MockConfigEntry,
    mock_listener: MagicMock,
) -> None:
    """Test the shared listener survives until the last entry is unloaded."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry_2.state is ConfigEntryState.LOADED
    mock_listener.start.assert_awaited_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_listener.stop.assert_not_awaited()

    await hass.config_entries.async_unload(mock_config_entry_2.entry_id)
    await hass.async_block_till_done()

    mock_listener.stop.assert_awaited_once()


async def test_unload_entry_keeps_listener_while_other_entry_sets_up(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test unloading an entry leaves a listener another setup already claimed."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    second_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST_2, CONF_SERIAL: MOCK_SERIAL_2},
        unique_id=MOCK_SERIAL_2,
    )
    second_entry.add_to_hass(hass)

    forwarding = asyncio.Event()
    resume = asyncio.Event()
    forward_entry_setups = ConfigEntries.async_forward_entry_setups

    async def blocked_forward_entry_setups(
        self: ConfigEntries, entry: MockConfigEntry, platforms: list[Platform]
    ) -> None:
        forwarding.set()
        await resume.wait()
        await forward_entry_setups(self, entry, platforms)

    with patch.object(
        ConfigEntries, "async_forward_entry_setups", blocked_forward_entry_setups
    ):
        setup = hass.async_create_task(
            hass.config_entries.async_setup(second_entry.entry_id)
        )
        await forwarding.wait()

        await hass.config_entries.async_unload(mock_config_entry.entry_id)

        mock_listener.stop.assert_not_awaited()

        resume.set()
        await setup

    await hass.async_block_till_done()

    assert second_entry.state is ConfigEntryState.LOADED
    mock_listener.stop.assert_not_awaited()


async def test_failed_setup_releases_listener(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test a setup that fails after starting the listener stops it again."""
    with patch.object(
        ConfigEntries,
        "async_forward_entry_setups",
        side_effect=RuntimeError("boom"),
        autospec=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_listener.stop.assert_awaited_once()


async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device info is correctly populated."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert device == snapshot


@pytest.mark.parametrize("mock_config_entry", [{CONF_MAC: MOCK_MAC}], indirect=True)
async def test_device_info_with_mac(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test MAC is added to device connections when stored in entry data."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:11:22:33") in device.connections


async def test_device_registry_not_updated_on_identical_callback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry is not updated when model/sw_version are unchanged."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    first_modified = device.modified_at

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.modified_at == first_modified


async def test_device_registry_updated_on_sw_version_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry is updated when sw_version changes."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "1.0.0"

    trigger_callback(mock_listener, sw_version="2.0.0")
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "2.0.0"
