"""Tests for the init module."""
import logging
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest
from pytest_unordered import unordered
from pytest_unordered import unordered
from pyvesync import VeSync

from homeassistant.components.vesync import (
    _async_new_device_discovery,
    _async_process_devices,
    async_setup_entry,
)
from homeassistant.components.vesync import (
    _async_new_device_discovery,
    _async_process_devices,
    async_setup_entry,
)
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

from .common import FAN_MODEL


async def test_async_setup_entry__not_login(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup does not create config entry when not logged in."""
    manager.login = Mock(return_value=False)

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as setups_mock, patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as setup_mock, patch(
        "homeassistant.components.vesync._async_process_devices"
    ) as process_mock:
        assert not await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()
        assert setups_mock.call_count == 0
        assert setup_mock.call_count == 0
        assert process_mock.call_count == 0

    assert manager.login.call_count == 1
    assert DOMAIN not in hass.data
    assert "Unable to login to the VeSync server" in caplog.text


async def test_async_setup_entry__no_devices(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync
) -> None:
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
) -> None:
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


async def test_async_process_devices__no_devices(
    hass: HomeAssistant, manager, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when manager with no devices is processed."""
    manager = MagicMock()
    with patch.object(
        hass, "async_add_executor_job", new=AsyncMock()
    ) as mock_add_executor_job:
        devices = await _async_process_devices(hass, manager)
        assert mock_add_executor_job.call_count == 1
        assert mock_add_executor_job.call_args[0][0] == manager.update

    assert devices == {
        "fans": [],
        "lights": [],
        "sensors": [],
        "switches": [],
    }
    assert caplog.messages[0] == "0 VeSync fans found"
    assert caplog.messages[1] == "0 VeSync lights found"
    assert caplog.messages[2] == "0 VeSync outlets found"
    assert caplog.messages[3] == "0 VeSync switches found"


async def test_async_process_devices__devices(
    hass: HomeAssistant, manager, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when manager with devices is processed."""
    caplog.set_level(logging.INFO)

    fan = MagicMock()
    fan.device_type = FAN_MODEL
    manager.fans = [fan]

    bulb = MagicMock()
    manager.bulbs = [bulb]

    outlet = MagicMock()
    manager.outlets = [outlet]

    switch = MagicMock()
    switch.is_dimmable.return_value = False
    light = MagicMock()
    light.is_dimmable.return_value = True
    manager.switches = [switch, light]

    with patch.object(
        hass, "async_add_executor_job", new=AsyncMock()
    ) as mock_add_executor_job:
        devices = await _async_process_devices(hass, manager)
        assert mock_add_executor_job.call_count == 1
        assert mock_add_executor_job.call_args[0][0] == manager.update

    assert devices == {
        "fans": [fan],
        "lights": [bulb, light],
        "sensors": [fan, outlet],
        "switches": [outlet, switch],
    }
    assert caplog.messages[0] == "1 VeSync fans found"
    assert caplog.messages[1] == "1 VeSync lights found"
    assert caplog.messages[2] == "1 VeSync outlets found"
    assert caplog.messages[3] == "2 VeSync switches found"


async def test_async_new_device_discovery__start_empty_discover_devices(
    hass: HomeAssistant,
    config_entry,
    manager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when manager with devices is processed."""
    caplog.set_level(logging.INFO)

    fan = MagicMock()
    fan.device_type = FAN_MODEL
    manager.fans = [fan]

    bulb = MagicMock()
    manager.bulbs = [bulb]

    outlet = MagicMock()
    manager.outlets = [outlet]

    switch = MagicMock()
    switch.is_dimmable.return_value = False
    light = MagicMock()
    light.is_dimmable.return_value = True
    manager.switches = [switch, light]

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_MANAGER] = manager
    hass.data[DOMAIN][VS_FANS]: list = []
    hass.data[DOMAIN][VS_LIGHTS]: list = []
    hass.data[DOMAIN][VS_SENSORS]: list = []
    hass.data[DOMAIN][VS_SWITCHES]: list = []

    mock_forward_setup = Mock()
    mock_service = Mock()
    with patch.object(
        hass, "async_add_executor_job", new=AsyncMock()
    ) as mock_add_executor_job, patch(
        "homeassistant.components.vesync.async_dispatcher_send"
    ) as mock_dispatcher_send, patch.object(
        hass, "async_create_task", new=Mock()
    ) as mock_create_task:
        await _async_new_device_discovery(
            hass, config_entry, mock_forward_setup, mock_service
        )
        assert mock_add_executor_job.call_count == 1
        assert mock_add_executor_job.call_args[0][0] == manager.update
        assert mock_dispatcher_send.call_count == 0
        assert mock_create_task.call_count == 4
        assert mock_forward_setup.call_count == 4
        mock_forward_setup.assert_has_calls(
            [
                call(config_entry, Platform.SWITCH),
                call(config_entry, Platform.FAN),
                call(config_entry, Platform.LIGHT),
                call(config_entry, Platform.SENSOR),
            ]
        )
        mock_service.assert_not_called()

    assert hass.data[DOMAIN][VS_FANS] == unordered([fan])
    assert hass.data[DOMAIN][VS_LIGHTS] == unordered([bulb, light])
    assert hass.data[DOMAIN][VS_SENSORS] == unordered([fan, outlet])
    assert hass.data[DOMAIN][VS_SWITCHES] == unordered([fan, outlet, switch])

    assert caplog.messages[0] == "1 VeSync fans found"
    assert caplog.messages[1] == "1 VeSync lights found"
    assert caplog.messages[2] == "1 VeSync outlets found"
    assert caplog.messages[3] == "2 VeSync switches found"


async def test_async_new_device_discovery__start_devices_discover_devices(
    hass: HomeAssistant,
    config_entry,
    manager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when manager with devices is processed."""
    caplog.set_level(logging.INFO)

    fan = MagicMock()
    fan.device_type = FAN_MODEL
    fan2 = MagicMock()
    fan2.device_type = FAN_MODEL
    manager.fans = [fan]

    bulb = MagicMock()
    bulb2 = MagicMock()
    manager.bulbs = [bulb]

    outlet = MagicMock()
    outlet2 = MagicMock()
    manager.outlets = [outlet]

    switch = MagicMock()
    switch.is_dimmable.return_value = False
    switch2 = MagicMock()
    switch2.is_dimmable.return_value = False
    light = MagicMock()
    light.is_dimmable.return_value = True
    light2 = MagicMock()
    light2.is_dimmable.return_value = True
    manager.switches = [switch, light]

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_MANAGER] = manager
    hass.data[DOMAIN][VS_FANS]: list = [fan2]
    hass.data[DOMAIN][VS_LIGHTS]: list = [bulb2, light2]
    hass.data[DOMAIN][VS_SENSORS]: list = [outlet2]
    hass.data[DOMAIN][VS_SWITCHES]: list = [switch2]

    mock_forward_setup = Mock()
    mock_service = Mock()
    with patch.object(
        hass, "async_add_executor_job", new=AsyncMock()
    ) as mock_add_executor_job, patch(
        "homeassistant.components.vesync.async_dispatcher_send"
    ) as mock_dispatcher_send, patch.object(
        hass, "async_create_task", new=Mock()
    ) as mock_create_task:
        await _async_new_device_discovery(
            hass, config_entry, mock_forward_setup, mock_service
        )
        assert mock_add_executor_job.call_count == 1
        assert mock_add_executor_job.call_args[0][0] == manager.update
        assert mock_dispatcher_send.call_count == 1
        assert mock_dispatcher_send.mock_calls[0] == call(
            hass,
            "vesync_discovery_switches",
            unordered([switch]),
        )
        assert mock_dispatcher_send.mock_calls[1] == call(
            hass, "vesync_discovery_fans", unordered([fan])
        )
        assert mock_dispatcher_send.mock_calls[2] == call(
            hass,
            "vesync_discovery_lights",
            unordered([fan, bulb, light]),
        )
        assert mock_dispatcher_send.mock_calls[5] == call(
            hass,
            "vesync_discovery_sensors",
            unordered([fan, outlet]),
        )
        assert mock_create_task.call_count == 0
        assert mock_forward_setup.call_count == 0
        mock_service.assert_not_called()

    assert hass.data[DOMAIN][VS_FANS] == unordered([fan, fan2])
    assert hass.data[DOMAIN][VS_LIGHTS] == unordered([fan, bulb, bulb2, light, light2])
    assert hass.data[DOMAIN][VS_SENSORS] == unordered([fan, outlet, outlet2])
    assert hass.data[DOMAIN][VS_SWITCHES] == unordered(
        [
            fan,
            outlet,
            switch,
            switch2,
        ]
    )

    assert caplog.messages[0] == "1 VeSync fans found"
    assert caplog.messages[1] == "1 VeSync lights found"
    assert caplog.messages[2] == "1 VeSync outlets found"
    assert caplog.messages[3] == "2 VeSync switches found"
