"""Tests for the Hot Spring integration."""

from typing import cast
from unittest.mock import MagicMock

from hotspring import HotSpringConnectionError, HotSpringError, Spa
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hotspring.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a successful setup entry and unload."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert cast(ConfigEntryState, init_integration.state) is ConfigEntryState.NOT_LOADED


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device registry entry creation with updated info."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "AA:BB:CC:DD:EE:FF"), init_integration.entry_id
    )
    assert device is not None
    assert device == snapshot


@pytest.mark.parametrize(
    "exception",
    [HotSpringConnectionError, HotSpringError],
)
async def test_async_setup_error(
    hass: HomeAssistant,
    mock_hotspring: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
) -> None:
    """Test a setup error when updating spa data."""
    mock_hotspring.update.side_effect = exception
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "root_topic",
    [
        "unknownTopic123",
        "mySpa112233445566",
    ],
)
async def test_async_setup_mac_mismatch(
    hass: HomeAssistant,
    mock_hotspring: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    root_topic: str,
) -> None:
    """Test setup fails when spa MAC is missing or mismatched."""
    device_fixture.info.root_topic = root_topic
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
