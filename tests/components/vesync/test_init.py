"""Tests for the init module."""

from unittest.mock import Mock, patch

import pytest
from pyvesync import VeSync

from homeassistant.components.vesync import SERVICE_UPDATE_DEVS, async_setup_entry
from homeassistant.components.vesync.const import DOMAIN, VS_DEVICES, VS_MANAGER
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


async def test_async_setup_entry__not_login(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup does not create config entry when not logged in."""
    manager.login = Mock(return_value=False)

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as setups_mock,
        patch(
            "homeassistant.components.vesync.async_generate_device_list"
        ) as process_mock,
    ):
        assert not await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()
        assert setups_mock.call_count == 0
        assert process_mock.call_count == 0

    assert manager.login.call_count == 1
    assert DOMAIN not in hass.data
    assert "Unable to login to the VeSync server" in caplog.text


async def test_async_setup_entry__no_devices(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync
) -> None:
    """Test setup connects to vesync and creates empty config when no devices."""
    with patch.object(hass.config_entries, "async_forward_entry_setups") as setups_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert setups_mock.call_count == 1
        assert setups_mock.call_args.args[0] == config_entry
        assert setups_mock.call_args.args[1] == [
            Platform.FAN,
            Platform.LIGHT,
            Platform.SENSOR,
            Platform.SWITCH,
        ]

    assert manager.login.call_count == 1
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert not hass.data[DOMAIN][VS_DEVICES]


async def test_async_setup_entry__loads_fans(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync, fan
) -> None:
    """Test setup connects to vesync and loads fan."""
    fans = [fan]
    manager.fans = fans
    manager._dev_list = {
        "fans": fans,
    }

    with patch.object(hass.config_entries, "async_forward_entry_setups") as setups_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert setups_mock.call_count == 1
        assert setups_mock.call_args.args[0] == config_entry
        assert setups_mock.call_args.args[1] == [
            Platform.FAN,
            Platform.LIGHT,
            Platform.SENSOR,
            Platform.SWITCH,
        ]
    assert manager.login.call_count == 1
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert hass.data[DOMAIN][VS_DEVICES] == [fan]


async def test_async_new_device_discovery__loads_fans(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync, fan
) -> None:
    """Test setup connects to vesync and loads fan as an update call."""

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    # Assert platforms loaded
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert not hass.data[DOMAIN][VS_DEVICES]
    fans = [fan]
    manager.fans = fans
    manager._dev_list = {
        "fans": fans,
    }
    await hass.services.async_call(DOMAIN, SERVICE_UPDATE_DEVS, {}, blocking=True)

    assert manager.login.call_count == 1
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert hass.data[DOMAIN][VS_DEVICES] == [fan]
