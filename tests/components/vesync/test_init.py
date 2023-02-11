"""Tests for the init module."""
from unittest.mock import Mock, patch

from pyvesync import VeSync

from homeassistant.components.vesync import async_setup_entry
from homeassistant.components.vesync.const import (
    DOMAIN,
    VS_FANS,
    VS_LIGHTS,
    VS_MANAGER,
    VS_SENSORS,
    VS_SWITCHES,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component


async def test_async_setup_component(hass: HomeAssistant, config: ConfigType):
    """Test setup component."""
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_async_setup_entry__not_login(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync, caplog
):
    """Test setup does not create config entry when not logged in."""
    manager.login = Mock(return_value=False)

    assert not await async_setup_entry(hass, config_entry)
    assert manager.login.call_count == 1
    assert DOMAIN not in hass.data
    assert "Unable to login to the VeSync server" in caplog.text


async def test_async_setup_entry__no_devices(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync
):
    """Test setup connects to vesync and creates empty config when no devices."""
    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as setups_mock, patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as setup_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert setups_mock.call_count == 1
        assert setups_mock.call_args.args[0] == config_entry
        assert setups_mock.call_args.args[1] == []
        assert setup_mock.call_count == 0
    assert manager.login.call_count == 1
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert not hass.data[DOMAIN][VS_SWITCHES]
    assert not hass.data[DOMAIN][VS_FANS]
    assert not hass.data[DOMAIN][VS_LIGHTS]
    assert not hass.data[DOMAIN][VS_SENSORS]


async def test_async_setup_entry__loads_fans(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync, fan
):
    """Test setup connects to vesync and loads fan platform."""
    fans = [fan]
    manager.fans = fans
    manager._dev_list = {
        "fans": fans,
    }

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as setups_mock, patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as setup_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert setups_mock.call_count == 1
        assert setups_mock.call_args.args[0] == config_entry
        assert setups_mock.call_args.args[1] == [Platform.FAN, Platform.SENSOR]
        assert setup_mock.call_count == 0
    assert manager.login.call_count == 1
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert not hass.data[DOMAIN][VS_SWITCHES]
    assert hass.data[DOMAIN][VS_FANS] == [fan]
    assert not hass.data[DOMAIN][VS_LIGHTS]
    assert hass.data[DOMAIN][VS_SENSORS] == [fan]


async def test_async_setup_entry__loads_bulbs(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync, bulb
):
    """Test setup connects to vesync and loads light platform."""
    bulbs = [bulb]
    manager.bulbs = bulbs
    manager._dev_list = {
        "bulbs": bulbs,
    }

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as setups_mock, patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as setup_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert setups_mock.call_count == 1
        assert setups_mock.call_args.args[0] == config_entry
        assert setups_mock.call_args.args[1] == [Platform.LIGHT]
        assert setup_mock.call_count == 0
    assert manager.login.call_count == 1
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert not hass.data[DOMAIN][VS_SWITCHES]
    assert not hass.data[DOMAIN][VS_FANS]
    assert hass.data[DOMAIN][VS_LIGHTS] == [bulb]
    assert not hass.data[DOMAIN][VS_SENSORS]


async def test_async_setup_entry__loads_switches(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    switch,
    dimmable_switch,
):
    """Test setup connects to vesync and loads switch platform."""
    switches = [switch, dimmable_switch]
    manager.switches = switches
    manager._dev_list = {
        "switches": switches,
    }

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as setups_mock, patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as setup_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert setups_mock.call_count == 1
        assert setups_mock.call_args.args[0] == config_entry
        assert setups_mock.call_args.args[1] == [Platform.SWITCH, Platform.LIGHT]
        assert setup_mock.call_count == 0
    assert manager.login.call_count == 1
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert hass.data[DOMAIN][VS_SWITCHES] == [switch]
    assert not hass.data[DOMAIN][VS_FANS]
    assert hass.data[DOMAIN][VS_LIGHTS] == [dimmable_switch]
    assert not hass.data[DOMAIN][VS_SENSORS]


async def test_async_setup_entry__loads_outlets(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync, outlet
):
    """Test setup connects to vesync and loads switch platform."""
    outlets = [outlet]
    manager.outlets = outlets
    manager._dev_list = {
        "outlets": outlets,
    }

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as setups_mock, patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as setup_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert setups_mock.call_count == 1
        assert setups_mock.call_args.args[0] == config_entry
        assert setups_mock.call_args.args[1] == [Platform.SWITCH, Platform.SENSOR]
        assert setup_mock.call_count == 0
    assert manager.login.call_count == 1
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert hass.data[DOMAIN][VS_SWITCHES] == [outlet]
    assert not hass.data[DOMAIN][VS_FANS]
    assert not hass.data[DOMAIN][VS_LIGHTS]
    assert hass.data[DOMAIN][VS_SENSORS] == [outlet]


# async def test_unload_entry(hass, config_entry, manager):
#     """Test entries are unloaded correctly."""
#     hass.data[DOMAIN] = {VS_MANAGER: manager}
#     with patch.object(
#         hass.config_entries, "async_forward_entry_unload", return_value=True
#     ) as unload:
#         assert await async_unload_entry(hass, config_entry)
#         await hass.async_block_till_done()
#         #        assert controller_manager.disconnect.call_count == 1
#         assert unload.call_count == 1
#     assert DOMAIN not in hass.data
