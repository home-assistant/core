"""Tests for the BT Home Hub 5 device tracker platform."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests

from homeassistant.components.bt_home_hub_5.const import DOMAIN
from homeassistant.components.bt_home_hub_5.device_tracker import async_setup_scanner
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant

MOCK_HOST = "192.168.1.254"
MAC_1 = "00:11:22:33:44:55"
MAC_2 = "AA:BB:CC:DD:EE:FF"
DEVICE_1 = {MAC_1: "Phone"}
DEVICE_BOTH = {MAC_1: "Phone", MAC_2: "Laptop"}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_entities(hass: HomeAssistant) -> None:
    """Test device tracker entities track connected status dynamically."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        title=f"BT Home Hub 5 ({MOCK_HOST})",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        return_value=DEVICE_1,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state_phone = hass.states.get("device_tracker.phone")
    assert state_phone is not None
    assert state_phone.state == STATE_HOME

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        return_value=DEVICE_BOTH,
    ):
        coordinator = entry.runtime_data
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state_laptop = hass.states.get("device_tracker.laptop")
    assert state_laptop is not None
    assert state_laptop.state == STATE_HOME

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        return_value={MAC_2: "Laptop"},
    ):
        coordinator = entry.runtime_data
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state_phone = hass.states.get("device_tracker.phone")
    assert state_phone is not None
    assert state_phone.state == STATE_NOT_HOME


async def test_coordinator_update_failure(hass: HomeAssistant) -> None:
    """Test coordinator handles connection exceptions correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        title=f"BT Home Hub 5 ({MOCK_HOST})",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        side_effect=requests.exceptions.ConnectionError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_data_none(hass: HomeAssistant) -> None:
    """Test coordinator handles None return value from get_devicelist."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        title=f"BT Home Hub 5 ({MOCK_HOST})",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_scanner_legacy(hass: HomeAssistant) -> None:
    """Test legacy YAML async_setup_scanner registers issue and creates import flow."""
    with (
        patch(
            "homeassistant.components.bt_home_hub_5.config_flow.get_devicelist",
            return_value=DEVICE_1,
        ),
        patch(
            "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
            return_value=DEVICE_1,
        ),
    ):
        result = await async_setup_scanner(
            hass, {CONF_HOST: MOCK_HOST}, see=None, discovery_info=None
        )
        assert result is True
        await hass.async_block_till_done()


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        title=f"BT Home Hub 5 ({MOCK_HOST})",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist",
        return_value=DEVICE_1,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
