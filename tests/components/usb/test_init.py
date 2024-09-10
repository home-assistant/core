"""Tests for the USB Discovery integration."""

import os
import sys
from unittest.mock import MagicMock, Mock, call, patch, sentinel

import pytest

from homeassistant.components import usb
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import conbee_device, slae_sh_device

from tests.typing import WebSocketGenerator


@pytest.fixture(name="operating_system")
def mock_operating_system():
    """Mock running Home Assistant Operating system."""
    with patch(
        "homeassistant.components.usb.system_info.async_get_system_info",
        return_value={
            "hassio": True,
            "docker": True,
        },
    ):
        yield


@pytest.fixture(name="docker")
def mock_docker():
    """Mock running Home Assistant in docker container."""
    with patch(
        "homeassistant.components.usb.system_info.async_get_system_info",
        return_value={
            "hassio": False,
            "docker": True,
        },
    ):
        yield


@pytest.fixture(name="venv")
def mock_venv():
    """Mock running Home Assistant in a venv container."""
    with patch(
        "homeassistant.components.usb.system_info.async_get_system_info",
        return_value={
            "hassio": False,
            "docker": False,
            "virtualenv": True,
        },
    ):
        yield


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Only works on linux",
)
async def test_observer_discovery(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, venv
) -> None:
    """Test that observer can discover a device without raising an exception."""
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
    mock_observer = None

    async def _mock_monitor_observer_callback(callback):
        await hass.async_add_executor_job(
            callback, MagicMock(action="create", device_path="/dev/new")
        )

    def _create_mock_monitor_observer(monitor, callback, name):
        nonlocal mock_observer
        hass.create_task(_mock_monitor_observer_callback(callback))
        mock_observer = MagicMock()
        return mock_observer

    with (
        patch("pyudev.Context"),
        patch("pyudev.MonitorObserver", new=_create_mock_monitor_observer),
        patch("pyudev.Monitor.filter_by"),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "test1"

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    # pylint:disable-next=unnecessary-dunder-call
    assert mock_observer.mock_calls == [call.start(), call.__bool__(), call.stop()]


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Only works on linux",
)
async def test_removal_by_observer_before_started(
    hass: HomeAssistant, operating_system
) -> None:
    """Test a device is removed by the observer before started."""

    async def _mock_monitor_observer_callback(callback):
        await hass.async_add_executor_job(
            callback, MagicMock(action="remove", device_path="/dev/new")
        )

    def _create_mock_monitor_observer(monitor, callback, name):
        hass.async_create_task(_mock_monitor_observer_callback(callback))

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

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch("pyudev.MonitorObserver", new=_create_mock_monitor_observer),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()

    with patch("homeassistant.components.usb.comports", return_value=[]):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()


async def test_discovered_by_websocket_scan(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan."""
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

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "test1"


async def test_discovered_by_websocket_scan_limited_by_description_matcher(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan is limited by the description matcher."""
    new_usb = [
        {"domain": "test1", "vid": "3039", "pid": "3039", "description": "*2652*"}
    ]

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

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "test1"


async def test_most_targeted_matcher_wins(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the most targeted matcher is used."""
    new_usb = [
        {"domain": "less", "vid": "3039", "pid": "3039"},
        {"domain": "more", "vid": "3039", "pid": "3039", "description": "*2652*"},
    ]

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

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "more"


async def test_discovered_by_websocket_scan_rejected_by_description_matcher(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan rejected by the description matcher."""
    new_usb = [
        {"domain": "test1", "vid": "3039", "pid": "3039", "description": "*not_it*"}
    ]

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

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0


async def test_discovered_by_websocket_scan_limited_by_serial_number_matcher(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan is limited by the serial_number matcher."""
    new_usb = [
        {
            "domain": "test1",
            "vid": "3039",
            "pid": "3039",
            "serial_number": "00_12_4b_00*",
        }
    ]

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

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "test1"


async def test_discovered_by_websocket_scan_rejected_by_serial_number_matcher(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan is rejected by the serial_number matcher."""
    new_usb = [
        {"domain": "test1", "vid": "3039", "pid": "3039", "serial_number": "123*"}
    ]

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

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0


async def test_discovered_by_websocket_scan_limited_by_manufacturer_matcher(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan is limited by the manufacturer matcher."""
    new_usb = [
        {
            "domain": "test1",
            "vid": "3039",
            "pid": "3039",
            "manufacturer": "dresden elektronik ingenieurtechnik*",
        }
    ]

    mock_comports = [
        MagicMock(
            device=conbee_device.device,
            vid=12345,
            pid=12345,
            serial_number=conbee_device.serial_number,
            manufacturer=conbee_device.manufacturer,
            description=conbee_device.description,
        )
    ]

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "test1"


async def test_discovered_by_websocket_scan_rejected_by_manufacturer_matcher(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan is rejected by the manufacturer matcher."""
    new_usb = [
        {
            "domain": "test1",
            "vid": "3039",
            "pid": "3039",
            "manufacturer": "other vendor*",
        }
    ]

    mock_comports = [
        MagicMock(
            device=conbee_device.device,
            vid=12345,
            pid=12345,
            serial_number=conbee_device.serial_number,
            manufacturer=conbee_device.manufacturer,
            description=conbee_device.description,
        )
    ]

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0


async def test_discovered_by_websocket_rejected_with_empty_serial_number_only(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket is rejected with empty serial number."""
    new_usb = [
        {"domain": "test1", "vid": "3039", "pid": "3039", "serial_number": "123*"}
    ]

    mock_comports = [
        MagicMock(
            device=conbee_device.device,
            vid=12345,
            pid=12345,
            serial_number=None,
            manufacturer=None,
            description=None,
        )
    ]

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0


async def test_discovered_by_websocket_scan_match_vid_only(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan only matching vid."""
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

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "test1"


async def test_discovered_by_websocket_scan_match_vid_wrong_pid(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan only matching vid but wrong pid."""
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

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0


async def test_discovered_by_websocket_no_vid_pid(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan with no vid or pid."""
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

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0


@pytest.mark.parametrize("exception_type", [ImportError, OSError])
async def test_non_matching_discovered_by_scanner_after_started(
    hass: HomeAssistant, exception_type, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a websocket scan that does not match."""
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

    with (
        patch("pyudev.Context", side_effect=exception_type),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Only works on linux",
)
async def test_observer_on_wsl_fallback_without_throwing_exception(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, venv
) -> None:
    """Test that observer on WSL failure results in fallback to scanning without raising an exception."""
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

    with (
        patch("pyudev.Context"),
        patch("pyudev.Monitor.filter_by", side_effect=ValueError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "test1"


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Only works on linux",
)
async def test_not_discovered_by_observer_before_started_on_docker(
    hass: HomeAssistant, docker
) -> None:
    """Test a device is not discovered since observer is not running on bare docker."""

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

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch("pyudev.MonitorObserver", new=_create_mock_monitor_observer),
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()

    with (
        patch("homeassistant.components.usb.comports", return_value=[]),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0


def test_get_serial_by_id_no_dir() -> None:
    """Test serial by id conversion if there's no /dev/serial/by-id."""
    p1 = patch("os.path.isdir", MagicMock(return_value=False))
    p2 = patch("os.scandir")
    with p1 as is_dir_mock, p2 as scan_mock:
        res = usb.get_serial_by_id(sentinel.path)
        assert res is sentinel.path
        assert is_dir_mock.call_count == 1
        assert scan_mock.call_count == 0


def test_get_serial_by_id() -> None:
    """Test serial by id conversion."""

    def _realpath(path):
        if path is sentinel.matched_link:
            return sentinel.path
        return sentinel.serial_link_path

    with (
        patch("os.path.isdir", MagicMock(return_value=True)) as is_dir_mock,
        patch("os.scandir") as scan_mock,
        patch("os.path.realpath", side_effect=_realpath),
    ):
        res = usb.get_serial_by_id(sentinel.path)
        assert res is sentinel.path
        assert is_dir_mock.call_count == 1
        assert scan_mock.call_count == 1

        entry1 = MagicMock(spec_set=os.DirEntry)
        entry1.is_symlink.return_value = True
        entry1.path = sentinel.some_path

        entry2 = MagicMock(spec_set=os.DirEntry)
        entry2.is_symlink.return_value = False
        entry2.path = sentinel.other_path

        entry3 = MagicMock(spec_set=os.DirEntry)
        entry3.is_symlink.return_value = True
        entry3.path = sentinel.matched_link

        scan_mock.return_value = [entry1, entry2, entry3]
        res = usb.get_serial_by_id(sentinel.path)
        assert res is sentinel.matched_link
        assert is_dir_mock.call_count == 2
        assert scan_mock.call_count == 2


def test_human_readable_device_name() -> None:
    """Test human readable device name includes the passed data."""
    name = usb.human_readable_device_name(
        "/dev/null",
        "612020FD",
        "Silicon Labs",
        "HubZ Smart Home Controller - HubZ Z-Wave Com Port",
        "10C4",
        "8A2A",
    )
    assert "/dev/null" in name
    assert "612020FD" in name
    assert "Silicon Labs" in name
    assert "HubZ Smart Home Controller - HubZ Z-Wave Com Port"[:26] in name
    assert "10C4" in name
    assert "8A2A" in name

    name = usb.human_readable_device_name(
        "/dev/null",
        "612020FD",
        "Silicon Labs",
        None,
        "10C4",
        "8A2A",
    )
    assert "/dev/null" in name
    assert "612020FD" in name
    assert "Silicon Labs" in name
    assert "10C4" in name
    assert "8A2A" in name


async def test_async_is_plugged_in(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test async_is_plugged_in."""
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

    matcher = {
        "vid": "3039",
        "pid": "3039",
    }

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=[]),
        patch.object(hass.config_entries.flow, "async_init"),
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert not usb.async_is_plugged_in(hass, matcher)

    with (
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch.object(hass.config_entries.flow, "async_init"),
    ):
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()
        assert usb.async_is_plugged_in(hass, matcher)


@pytest.mark.parametrize(
    "matcher",
    [
        {"vid": "abcd"},
        {"pid": "123a"},
        {"serial_number": "1234ABCD"},
        {"manufacturer": "Some Manufacturer"},
        {"description": "A description"},
    ],
)
async def test_async_is_plugged_in_case_enforcement(
    hass: HomeAssistant, matcher
) -> None:
    """Test `async_is_plugged_in` throws an error when incorrect cases are used."""

    new_usb = [{"domain": "test1", "vid": "ABCD"}]

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=[]),
        patch.object(hass.config_entries.flow, "async_init"),
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        with pytest.raises(ValueError):
            usb.async_is_plugged_in(hass, matcher)


async def test_web_socket_triggers_discovery_request_callbacks(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the websocket call triggers a discovery request callback."""
    mock_callback = Mock()

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=[]),
        patch("homeassistant.components.usb.comports", return_value=[]),
        patch.object(hass.config_entries.flow, "async_init"),
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        cancel = usb.async_register_scan_request_callback(hass, mock_callback)

        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

        assert len(mock_callback.mock_calls) == 1
        cancel()

        await ws_client.send_json({"id": 2, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()
        assert len(mock_callback.mock_calls) == 1


async def test_initial_scan_callback(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test it's possible to register a callback when the initial scan is done."""
    mock_callback_1 = Mock()
    mock_callback_2 = Mock()

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=[]),
        patch("homeassistant.components.usb.comports", return_value=[]),
        patch.object(hass.config_entries.flow, "async_init"),
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        cancel_1 = usb.async_register_initial_scan_callback(hass, mock_callback_1)
        assert len(mock_callback_1.mock_calls) == 0

        await hass.async_block_till_done()
        assert len(mock_callback_1.mock_calls) == 0

        # This triggers the initial scan
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert len(mock_callback_1.mock_calls) == 1

        # A callback registered now should be called immediately. The old callback
        # should not be called again
        cancel_2 = usb.async_register_initial_scan_callback(hass, mock_callback_2)
        assert len(mock_callback_1.mock_calls) == 1
        assert len(mock_callback_2.mock_calls) == 1

        # Calling the cancels should be allowed even if the callback has been called
        cancel_1()
        cancel_2()


async def test_cancel_initial_scan_callback(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test it's possible to cancel an initial scan callback."""
    mock_callback = Mock()

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=[]),
        patch("homeassistant.components.usb.comports", return_value=[]),
        patch.object(hass.config_entries.flow, "async_init"),
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        cancel = usb.async_register_initial_scan_callback(hass, mock_callback)
        assert len(mock_callback.mock_calls) == 0

        await hass.async_block_till_done()
        assert len(mock_callback.mock_calls) == 0
        cancel()

        # This triggers the initial scan
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert len(mock_callback.mock_calls) == 0


async def test_resolve_serial_by_id(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the discovery data resolves to serial/by-id."""
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

    with (
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=mock_comports),
        patch(
            "homeassistant.components.usb.get_serial_by_id",
            return_value="/dev/serial/by-id/bla",
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "test1"
    assert mock_config_flow.mock_calls[0][2]["data"].device == "/dev/serial/by-id/bla"


@pytest.mark.parametrize(
    "ports",
    [
        [
            MagicMock(
                device="/dev/cu.usbserial-2120",
                vid=0x3039,
                pid=0x3039,
                serial_number=conbee_device.serial_number,
                manufacturer=conbee_device.manufacturer,
                description=conbee_device.description,
            ),
            MagicMock(
                device="/dev/cu.usbserial-1120",
                vid=0x3039,
                pid=0x3039,
                serial_number=slae_sh_device.serial_number,
                manufacturer=slae_sh_device.manufacturer,
                description=slae_sh_device.description,
            ),
            MagicMock(
                device="/dev/cu.SLAB_USBtoUART",
                vid=0x3039,
                pid=0x3039,
                serial_number=conbee_device.serial_number,
                manufacturer=conbee_device.manufacturer,
                description=conbee_device.description,
            ),
            MagicMock(
                device="/dev/cu.SLAB_USBtoUART2",
                vid=0x3039,
                pid=0x3039,
                serial_number=slae_sh_device.serial_number,
                manufacturer=slae_sh_device.manufacturer,
                description=slae_sh_device.description,
            ),
        ],
        [
            MagicMock(
                device="/dev/cu.SLAB_USBtoUART2",
                vid=0x3039,
                pid=0x3039,
                serial_number=slae_sh_device.serial_number,
                manufacturer=slae_sh_device.manufacturer,
                description=slae_sh_device.description,
            ),
            MagicMock(
                device="/dev/cu.SLAB_USBtoUART",
                vid=0x3039,
                pid=0x3039,
                serial_number=conbee_device.serial_number,
                manufacturer=conbee_device.manufacturer,
                description=conbee_device.description,
            ),
            MagicMock(
                device="/dev/cu.usbserial-1120",
                vid=0x3039,
                pid=0x3039,
                serial_number=slae_sh_device.serial_number,
                manufacturer=slae_sh_device.manufacturer,
                description=slae_sh_device.description,
            ),
            MagicMock(
                device="/dev/cu.usbserial-2120",
                vid=0x3039,
                pid=0x3039,
                serial_number=conbee_device.serial_number,
                manufacturer=conbee_device.manufacturer,
                description=conbee_device.description,
            ),
        ],
    ],
)
async def test_cp2102n_ordering_on_macos(
    ports: list[MagicMock], hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test CP2102N ordering on macOS."""

    new_usb = [
        {"domain": "test1", "vid": "3039", "pid": "3039", "description": "*2652*"}
    ]

    with (
        patch("sys.platform", "darwin"),
        patch("pyudev.Context", side_effect=ImportError),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch("homeassistant.components.usb.comports", return_value=ports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "test1"

    # We always use `cu.SLAB_USBtoUART`
    assert mock_config_flow.mock_calls[0][2]["data"].device == "/dev/cu.SLAB_USBtoUART2"
