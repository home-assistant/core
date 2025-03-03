"""Tests for the Slide Local integration."""

from unittest.mock import AsyncMock

from goslideapi.goslideapi import ClientConnectionError
from syrupy import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_platform

from tests.common import MockConfigEntry


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_platform(hass, mock_config_entry, [Platform.COVER])
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "1234567890ab")}
    )
    assert device_entry is not None
    assert device_entry == snapshot


async def test_raise_config_entry_not_ready_when_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_slide_api: AsyncMock,
) -> None:
    """Config entry state is SETUP_RETRY when slide is offline."""

    mock_slide_api.slide_info.side_effect = [ClientConnectionError, None]

    await setup_platform(hass, mock_config_entry, [Platform.COVER])
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_raise_config_entry_not_ready_when_empty_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_slide_api: AsyncMock,
) -> None:
    """Config entry state is SETUP_RETRY when slide is offline."""

    mock_slide_api.slide_info.return_value = None

    await setup_platform(hass, mock_config_entry, [Platform.COVER])
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    assert len(hass.config_entries.flow.async_progress()) == 0
