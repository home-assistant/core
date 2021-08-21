"""Tests for the USB Discovery integration."""
import datetime
import sys
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import slae_sh_device

from tests.common import async_fire_time_changed


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Only works on linux",
)
async def test_discovered_by_observer_before_started(hass):
    """Test a device is discovered by the observer before started."""

    async def _mock_monitor_observer_callback(callback):
        await hass.async_add_executor_job(
            callback, MagicMock(action="add", device_path="/dev/new")
        )

    def _create_mock_monitor_observer(monitor, callback, name):
        hass.async_create_task(_mock_monitor_observer_callback(callback))
        return MagicMock()

    new_usb = [{"domain": "test1", "vid": "3039", "pid": "3039"}]

    mock_comports = [
        MagicMock(
            device=slae_sh_device.device,
            vid=12345,
            pid=12345,
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with patch(
        "homeassistant.components.usb.async_get_usb", return_value=new_usb
    ), patch(
        "homeassistant.components.usb.comports", return_value=mock_comports
    ), patch(
        "pyudev.MonitorObserver", new=_create_mock_monitor_observer
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()

    with patch("homeassistant.components.usb.comports", return_value=[]), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "test1"


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Only works on linux",
)
async def test_removal_by_observer_before_started(hass):
    """Test a device is removed by the observer before started."""

    async def _mock_monitor_observer_callback(callback):
        await hass.async_add_executor_job(
            callback, MagicMock(action="remove", device_path="/dev/new")
        )

    def _create_mock_monitor_observer(monitor, callback, name):
        hass.async_create_task(_mock_monitor_observer_callback(callback))
        return MagicMock()

    new_usb = [{"domain": "test1", "vid": "3039", "pid": "3039"}]

    mock_comports = [
        MagicMock(
            device=slae_sh_device.device,
            vid=12345,
            pid=12345,
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with patch(
        "homeassistant.components.usb.async_get_usb", return_value=new_usb
    ), patch(
        "homeassistant.components.usb.comports", return_value=mock_comports
    ), patch(
        "pyudev.MonitorObserver", new=_create_mock_monitor_observer
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow:
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()

    with patch("homeassistant.components.usb.comports", return_value=[]):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0


async def test_discovered_by_scanner_after_started(hass):
    """Test a device is discovered by the scanner after the started event."""
    new_usb = [{"domain": "test1", "vid": "3039", "pid": "3039"}]

    mock_comports = [
        MagicMock(
            device=slae_sh_device.device,
            vid=12345,
            pid=12345,
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with patch("pyudev.Context", side_effect=ImportError), patch(
        "homeassistant.components.usb.async_get_usb", return_value=new_usb
    ), patch(
        "homeassistant.components.usb.comports", return_value=mock_comports
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow:
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=1))
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "test1"


async def test_discovered_by_scanner_after_started_match_vid_only(hass):
    """Test a device is discovered by the scanner after the started event only matching vid."""
    new_usb = [{"domain": "test1", "vid": "3039"}]

    mock_comports = [
        MagicMock(
            device=slae_sh_device.device,
            vid=12345,
            pid=12345,
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with patch("pyudev.Context", side_effect=ImportError), patch(
        "homeassistant.components.usb.async_get_usb", return_value=new_usb
    ), patch(
        "homeassistant.components.usb.comports", return_value=mock_comports
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow:
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=1))
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "test1"


async def test_discovered_by_scanner_after_started_match_vid_wrong_pid(hass):
    """Test a device is discovered by the scanner after the started event only matching vid but wrong pid."""
    new_usb = [{"domain": "test1", "vid": "3039", "pid": "9999"}]

    mock_comports = [
        MagicMock(
            device=slae_sh_device.device,
            vid=12345,
            pid=12345,
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with patch("pyudev.Context", side_effect=ImportError), patch(
        "homeassistant.components.usb.async_get_usb", return_value=new_usb
    ), patch(
        "homeassistant.components.usb.comports", return_value=mock_comports
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow:
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=1))
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0


async def test_discovered_by_scanner_after_started_no_vid_pid(hass):
    """Test a device is discovered by the scanner after the started event with no vid or pid."""
    new_usb = [{"domain": "test1", "vid": "3039", "pid": "9999"}]

    mock_comports = [
        MagicMock(
            device=slae_sh_device.device,
            vid=None,
            pid=None,
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with patch("pyudev.Context", side_effect=ImportError), patch(
        "homeassistant.components.usb.async_get_usb", return_value=new_usb
    ), patch(
        "homeassistant.components.usb.comports", return_value=mock_comports
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow:
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=1))
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0


@pytest.mark.parametrize("exception_type", [ImportError, OSError])
async def test_non_matching_discovered_by_scanner_after_started(hass, exception_type):
    """Test a device is discovered by the scanner after the started event that does not match."""
    new_usb = [{"domain": "test1", "vid": "4444", "pid": "4444"}]

    mock_comports = [
        MagicMock(
            device=slae_sh_device.device,
            vid=12345,
            pid=12345,
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with patch("pyudev.Context", side_effect=exception_type), patch(
        "homeassistant.components.usb.async_get_usb", return_value=new_usb
    ), patch(
        "homeassistant.components.usb.comports", return_value=mock_comports
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow:
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=1))
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0
