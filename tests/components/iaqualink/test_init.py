"""Tests for iAqualink integration."""

import asyncio
from unittest.mock import patch

from iaqualink.device import (
    AqualinkAuxToggle,
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkLightToggle,
    AqualinkSensor,
    AqualinkThermostat,
)
from iaqualink.exception import AqualinkServiceException

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.iaqualink import DOMAIN, UPDATE_INTERVAL, AqualinkEntity
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.iaqualink.conftest import (
    async_raises,
    async_returns,
    get_aqualink_client,
    get_aqualink_device,
    get_aqualink_system,
)


def _ffwd_next_update_interval(hass):
    now = dt_util.utcnow()
    async_fire_time_changed(hass, now + UPDATE_INTERVAL)


async def test_setup_login_exception(hass, config_entry):
    """Test setup encountering a login exception."""
    config_entry.add_to_hass(hass)

    with patch(
        "iaqualink.client.AqualinkClient.login",
        side_effect=AqualinkServiceException,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_setup_login_timeout(hass, config_entry):
    """Test setup encountering a timeout while logging in."""
    config_entry.add_to_hass(hass)

    with patch(
        "iaqualink.client.AqualinkClient.login",
        side_effect=asyncio.TimeoutError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_systems_exception(hass, config_entry):
    """Test setup encountering an exception while retrieving systems."""
    config_entry.add_to_hass(hass)

    with patch("iaqualink.client.AqualinkClient.login", return_value=None), patch(
        "iaqualink.client.AqualinkClient.get_systems",
        side_effect=AqualinkServiceException,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_no_systems_recognized(hass, config_entry):
    """Test setup ending in no systems recognized."""
    config_entry.add_to_hass(hass)

    with patch("iaqualink.client.AqualinkClient.login", return_value=None), patch(
        "iaqualink.client.AqualinkClient.get_systems",
        return_value={},
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_setup_devices_exception(hass, config_entry):
    """Test setup encountering an exception while retrieving devices."""
    config_entry.add_to_hass(hass)

    client = get_aqualink_client()
    system = get_aqualink_system(client)
    systems = {system.serial: system}

    with patch("iaqualink.client.AqualinkClient.login", return_value=None), patch(
        "iaqualink.client.AqualinkClient.get_systems", return_value=systems
    ), patch(
        "iaqualink.system.AqualinkSystem.get_devices",
        side_effect=AqualinkServiceException,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_all_good_no_recognized_devices(hass, config_entry):
    """Test setup ending in no devices recognized."""
    config_entry.add_to_hass(hass)

    client = get_aqualink_client()
    system = get_aqualink_system(client)
    systems = {system.serial: system}
    device = get_aqualink_device(system, AqualinkDevice)
    devices = {device.name: device}

    with patch("iaqualink.client.AqualinkClient.login", return_value=None), patch(
        "iaqualink.client.AqualinkClient.get_systems", return_value=systems
    ), patch("iaqualink.system.AqualinkSystem.get_devices", return_value=devices):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED

    assert hass.data[DOMAIN][BINARY_SENSOR_DOMAIN] == []
    assert hass.data[DOMAIN][CLIMATE_DOMAIN] == []
    assert hass.data[DOMAIN][LIGHT_DOMAIN] == []
    assert hass.data[DOMAIN][SENSOR_DOMAIN] == []
    assert hass.data[DOMAIN][SWITCH_DOMAIN] == []

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data


async def test_setup_all_good_all_device_types(hass, config_entry):
    """Test setup ending in one device of each type recognized."""
    config_entry.add_to_hass(hass)

    client = get_aqualink_client()
    system = get_aqualink_system(client)
    systems = {system.serial: system}
    devices = [
        get_aqualink_device(system, AqualinkDevice),
        get_aqualink_device(system, AqualinkAuxToggle),
        get_aqualink_device(system, AqualinkBinarySensor),
        get_aqualink_device(system, AqualinkLightToggle),
        get_aqualink_device(system, AqualinkSensor),
        get_aqualink_device(system, AqualinkThermostat),
    ]
    devices = {d.name: d for d in devices}

    with patch("iaqualink.client.AqualinkClient.login", return_value=None), patch(
        "iaqualink.client.AqualinkClient.get_systems", return_value=systems
    ), patch("iaqualink.system.AqualinkSystem.get_devices", return_value=devices):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED

    assert len(hass.data[DOMAIN][BINARY_SENSOR_DOMAIN]) == 1
    assert len(hass.data[DOMAIN][CLIMATE_DOMAIN]) == 1
    assert len(hass.data[DOMAIN][LIGHT_DOMAIN]) == 1
    assert len(hass.data[DOMAIN][SENSOR_DOMAIN]) == 1
    assert len(hass.data[DOMAIN][SWITCH_DOMAIN]) == 1

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data


async def test_multiple_updates(hass, config_entry):
    """Test all possible results of online status transition after update."""
    config_entry.add_to_hass(hass)

    client = get_aqualink_client()
    system = get_aqualink_system(client)
    systems = {system.serial: system}

    with patch("iaqualink.client.AqualinkClient.login", return_value=None), patch(
        "iaqualink.client.AqualinkClient.get_systems", return_value=systems
    ), patch("iaqualink.system.AqualinkSystem.get_devices", return_value={}):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED

    def set_online_to_true():
        system.online = True

    def set_online_to_false():
        system.online = False

    # True -> True
    system.online = True
    with patch(
        "iaqualink.system.AqualinkSystem.update", side_effect=set_online_to_true
    ), patch("homeassistant.components.iaqualink._LOGGER.warning") as mock_warn:
        _ffwd_next_update_interval(hass)
        await hass.async_block_till_done()
        mock_warn.assert_not_called()

    # True -> False
    system.online = True
    with patch(
        "iaqualink.system.AqualinkSystem.update", side_effect=set_online_to_false
    ), patch("homeassistant.components.iaqualink._LOGGER.warning") as mock_warn:
        _ffwd_next_update_interval(hass)
        await hass.async_block_till_done()
        mock_warn.assert_not_called()

    # True -> None / ServiceException
    system.online = True
    with patch(
        "iaqualink.system.AqualinkSystem.update",
        side_effect=AqualinkServiceException,
    ), patch("homeassistant.components.iaqualink._LOGGER.warning") as mock_warn:
        _ffwd_next_update_interval(hass)
        await hass.async_block_till_done()
        mock_warn.assert_called_once()

    # False -> False
    system.online = False
    with patch(
        "iaqualink.system.AqualinkSystem.update", side_effect=set_online_to_false
    ), patch("homeassistant.components.iaqualink._LOGGER.warning") as mock_warn:
        _ffwd_next_update_interval(hass)
        await hass.async_block_till_done()
        mock_warn.assert_not_called()

    # False -> True
    system.online = False
    with patch(
        "iaqualink.system.AqualinkSystem.update", side_effect=set_online_to_true
    ), patch("homeassistant.components.iaqualink._LOGGER.warning") as mock_warn:
        _ffwd_next_update_interval(hass)
        await hass.async_block_till_done()
        mock_warn.assert_called_once()

    # False -> None / ServiceException
    system.online = False
    with patch(
        "iaqualink.system.AqualinkSystem.update",
        side_effect=AqualinkServiceException,
    ), patch("homeassistant.components.iaqualink._LOGGER.warning") as mock_warn:
        _ffwd_next_update_interval(hass)
        await hass.async_block_till_done()
        mock_warn.assert_called_once()

    # None -> None / ServiceException
    system.online = None
    with patch(
        "iaqualink.system.AqualinkSystem.update",
        side_effect=AqualinkServiceException,
    ), patch("homeassistant.components.iaqualink._LOGGER.warning") as mock_warn:
        _ffwd_next_update_interval(hass)
        await hass.async_block_till_done()
        mock_warn.assert_called_once()

    # None -> True
    system.online = None
    with patch(
        "iaqualink.system.AqualinkSystem.update", side_effect=set_online_to_true
    ), patch("homeassistant.components.iaqualink._LOGGER.warning") as mock_warn:

        _ffwd_next_update_interval(hass)
        await hass.async_block_till_done()
        mock_warn.assert_called_once()

    # None -> False
    system.online = None
    with patch(
        "iaqualink.system.AqualinkSystem.update", side_effect=set_online_to_false
    ), patch("homeassistant.components.iaqualink._LOGGER.warning") as mock_warn:
        _ffwd_next_update_interval(hass)
        await hass.async_block_till_done()
        mock_warn.assert_not_called()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data


async def test_entity_assumed_and_available(hass):
    """Test assumed_state and_available properties for all values of online."""
    client = get_aqualink_client()
    system = get_aqualink_system(client)
    light = get_aqualink_device(system, AqualinkLightToggle)
    ha_light = AqualinkEntity(light)

    # None means maybe.
    light.system.online = None
    assert ha_light.assumed_state is True
    assert ha_light.available is False

    light.system.online = False
    assert ha_light.assumed_state is True
    assert ha_light.available is False

    light.system.online = True
    assert ha_light.assumed_state is False
    assert ha_light.available is True


async def test_safe_exec(hass):
    """Test assumed_state and_available properties for all values of online."""
    client = get_aqualink_client()
    system = get_aqualink_system(client)
    light = get_aqualink_device(system, AqualinkLightToggle)
    ha_light = AqualinkEntity(light)

    with patch("homeassistant.components.iaqualink._LOGGER.warning") as mock_warn:
        async_noop = async_returns(None)
        await ha_light.safe_exec(async_noop())
        mock_warn.assert_not_called()

    with patch("homeassistant.components.iaqualink._LOGGER.warning") as mock_warn:
        async_ex = async_raises(AqualinkServiceException)
        await ha_light.safe_exec(async_ex())
        mock_warn.assert_called_once()
