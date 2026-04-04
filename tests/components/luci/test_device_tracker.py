"""Tests for the luci device tracker."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import MOCK_DEVICE_1, MOCK_DEVICE_2

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luci_client: MagicMock,
) -> None:
    """Test device tracker entities are created."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.luci.OpenWrtRpc",
        return_value=mock_luci_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.device1")
    assert state is not None
    assert state.state == STATE_HOME

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.device2")
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_disconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luci_client: MagicMock,
) -> None:
    """Test device goes not_home when disconnected."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.luci.OpenWrtRpc",
        return_value=mock_luci_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.device1")
    assert state is not None
    assert state.state == STATE_HOME

    # Simulate device disconnecting
    mock_luci_client.get_all_connected_devices.return_value = [MOCK_DEVICE_2]

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.device1")
    assert state is not None
    assert state.state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_new_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luci_client: MagicMock,
) -> None:
    """Test new device is added on coordinator update."""
    mock_luci_client.get_all_connected_devices.return_value = [MOCK_DEVICE_1]
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.luci.OpenWrtRpc",
        return_value=mock_luci_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Only device1 should exist
    assert hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.device1") is not None
    assert hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.device2") is None

    # Add device2 and trigger an update
    mock_luci_client.get_all_connected_devices.return_value = [
        MOCK_DEVICE_1,
        MOCK_DEVICE_2,
    ]

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.device2")
    assert state is not None
    assert state.state == STATE_HOME


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luci_client: MagicMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.luci.OpenWrtRpc",
        return_value=mock_luci_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
