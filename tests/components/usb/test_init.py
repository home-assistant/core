"""Tests for the USB Discovery integration."""

import asyncio
from datetime import timedelta
import logging
import os
from typing import Any
from unittest.mock import MagicMock, Mock, call, patch, sentinel

import pytest

from homeassistant.components import usb
from homeassistant.components.usb.models import USBDevice
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.usb import UsbServiceInfo
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    force_usb_polling_watcher,  # noqa: F401
    patch_scanned_serial_ports,
)

from tests.common import async_fire_time_changed, import_and_test_deprecated_constant
from tests.typing import WebSocketGenerator

conbee_device = USBDevice(
    device="/dev/cu.usbmodemDE24338801",
    vid="1CF1",
    pid="0030",
    serial_number="DE2433880",
    manufacturer="dresden elektronik ingenieurtechnik GmbH",
    description="ConBee II",
)
slae_sh_device = USBDevice(
    device="/dev/cu.usbserial-110",
    vid="10C4",
    pid="EA60",
    serial_number="00_12_4B_00_22_98_88_7F",
    manufacturer="Silicon Labs",
    description="slae.sh cc2652rb stick - slaesh's iot stuff",
)


async def test_aiousbwatcher_discovery(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that aiousbwatcher can discover a device without raising an exception."""
    new_usb = [{"domain": "test1", "vid": "3039"}, {"domain": "test2", "vid": "0FA0"}]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    aiousbwatcher_callback = None

    def async_register_callback(callback):
        nonlocal aiousbwatcher_callback
        aiousbwatcher_callback = callback

    MockAIOUSBWatcher = MagicMock()
    MockAIOUSBWatcher.async_register_callback = async_register_callback

    with (
        patch("sys.platform", "linux"),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
        patch(
            "homeassistant.components.usb.AIOUSBWatcher", return_value=MockAIOUSBWatcher
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert aiousbwatcher_callback is not None

        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "test1"
        await hass.async_block_till_done()
        assert len(mock_config_flow.mock_calls) == 1

        mock_ports.append(
            USBDevice(
                device=slae_sh_device.device,
                vid="0FA0",
                pid="0FA0",
                serial_number=slae_sh_device.serial_number,
                manufacturer=slae_sh_device.manufacturer,
                description=slae_sh_device.description,
            )
        )

        aiousbwatcher_callback()
        await hass.async_block_till_done()

        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=usb.ADD_REMOVE_SCAN_COOLDOWN)
        )
        await hass.async_block_till_done(wait_background_tasks=True)

        assert len(mock_config_flow.mock_calls) == 2
        assert mock_config_flow.mock_calls[1][1][0] == "test2"

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_polling_discovery(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that polling can discover a device without raising an exception."""
    new_usb = [{"domain": "test1", "vid": "3039"}]
    mock_comports_found_device = asyncio.Event()

    def scan_serial_ports() -> list:
        nonlocal mock_ports

        # Only "find" a device after a few invocations
        if len(mock_ports.mock_calls) < 5:
            return []

        mock_comports_found_device.set()
        return [
            USBDevice(
                device=slae_sh_device.device,
                vid="3039",
                pid="3039",
                serial_number=slae_sh_device.serial_number,
                manufacturer=slae_sh_device.manufacturer,
                description=slae_sh_device.description,
            )
        ]

    with (
        patch("sys.platform", "linux"),
        patch(
            "homeassistant.components.usb.POLLING_MONITOR_SCAN_PERIOD",
            timedelta(seconds=0.01),
        ),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(side_effect=scan_serial_ports) as mock_ports,
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        # Wait until a new device is discovered after a few polling attempts
        assert len(mock_config_flow.mock_calls) == 0
        await mock_comports_found_device.wait()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "test1"

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_removal_by_aiousbwatcher_before_started(hass: HomeAssistant) -> None:
    """Test a device is removed by the aiousbwatcher before started."""
    new_usb = [{"domain": "test1", "vid": "3039", "pid": "3039"}]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()

    with patch_scanned_serial_ports(return_value=[]):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_discovered_by_websocket_scan(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan."""
    new_usb = [{"domain": "test1", "vid": "3039", "pid": "3039"}]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_discovered_by_websocket_scan_limited_by_description_matcher(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan is limited by the description matcher."""
    new_usb = [
        {"domain": "test1", "vid": "3039", "pid": "3039", "description": "*2652*"}
    ]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_most_targeted_matcher_wins(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the most targeted matcher is used."""
    new_usb = [
        {"domain": "less", "vid": "3039", "pid": "3039"},
        {"domain": "more", "vid": "3039", "pid": "3039", "description": "*2652*"},
    ]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_discovered_by_websocket_scan_rejected_by_description_matcher(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan rejected by the description matcher."""
    new_usb = [
        {"domain": "test1", "vid": "3039", "pid": "3039", "description": "*not_it*"}
    ]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
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

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_discovered_by_websocket_scan_rejected_by_serial_number_matcher(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan is rejected by the serial_number matcher."""
    new_usb = [
        {"domain": "test1", "vid": "3039", "pid": "3039", "serial_number": "123*"}
    ]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
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

    mock_ports = [
        USBDevice(
            device=conbee_device.device,
            vid="3039",
            pid="3039",
            serial_number=conbee_device.serial_number,
            manufacturer=conbee_device.manufacturer,
            description=conbee_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
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

    mock_ports = [
        USBDevice(
            device=conbee_device.device,
            vid="3039",
            pid="3039",
            serial_number=conbee_device.serial_number,
            manufacturer=conbee_device.manufacturer,
            description=conbee_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_discovered_by_websocket_rejected_with_empty_serial_number_only(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket is rejected with empty serial number."""
    new_usb = [
        {"domain": "test1", "vid": "3039", "pid": "3039", "serial_number": "123*"}
    ]

    mock_ports = [
        USBDevice(
            device=conbee_device.device,
            vid="3039",
            pid="3039",
            serial_number=None,
            manufacturer=None,
            description=None,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_discovered_by_websocket_scan_match_vid_only(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan only matching vid."""
    new_usb = [{"domain": "test1", "vid": "3039"}]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_discovered_by_websocket_scan_match_vid_wrong_pid(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan only matching vid but wrong pid."""
    new_usb = [{"domain": "test1", "vid": "3039", "pid": "9999"}]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_discovered_by_websocket_no_vid_pid(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a device is discovered from websocket scan with no vid or pid."""
    new_usb = [{"domain": "test1", "vid": "3039", "pid": "9999"}]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid=None,
            pid=None,
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_non_matching_discovered_by_scanner_after_started(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a websocket scan that does not match."""
    new_usb = [{"domain": "test1", "vid": "4444", "pid": "4444"}]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


async def test_aiousbwatcher_on_wsl_fallback_without_throwing_exception(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that aiousbwatcher on WSL failure results in fallback to scanning without raising an exception."""
    new_usb = [{"domain": "test1", "vid": "3039"}]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


async def test_discovered_by_aiousbwatcher_before_started(hass: HomeAssistant) -> None:
    """Test a device is discovered since aiousbwatcher is now running."""
    new_usb = [{"domain": "test1", "vid": "3039", "pid": "3039"}]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]
    initial_ports = []
    aiousbwatcher_callback = None

    def async_register_callback(callback):
        nonlocal aiousbwatcher_callback
        aiousbwatcher_callback = callback

    MockAIOUSBWatcher = MagicMock()
    MockAIOUSBWatcher.async_register_callback = async_register_callback

    with (
        patch("sys.platform", "linux"),
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=initial_ports),
        patch(
            "homeassistant.components.usb.AIOUSBWatcher", return_value=MockAIOUSBWatcher
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(mock_config_flow.mock_calls) == 0

        initial_ports.extend(mock_ports)
        aiousbwatcher_callback()
        await hass.async_block_till_done()

        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=usb.ADD_REMOVE_SCAN_COOLDOWN)
        )
        await hass.async_block_till_done(wait_background_tasks=True)

        assert len(mock_config_flow.mock_calls) == 1


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


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_async_is_plugged_in(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test async_is_plugged_in."""
    new_usb = [{"domain": "test1", "vid": "3039", "pid": "3039"}]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
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
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=[]),
        patch.object(hass.config_entries.flow, "async_init"),
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert not usb.async_is_plugged_in(hass, matcher)

    with (
        patch_scanned_serial_ports(return_value=mock_ports),
        patch.object(hass.config_entries.flow, "async_init"),
    ):
        ws_client = await hass_ws_client(hass)
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()
        assert usb.async_is_plugged_in(hass, matcher)


@pytest.mark.usefixtures("force_usb_polling_watcher")
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
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=[]),
        patch.object(hass.config_entries.flow, "async_init"),
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        with pytest.raises(ValueError):
            usb.async_is_plugged_in(hass, matcher)


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_web_socket_triggers_discovery_request_callbacks(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the websocket call triggers a discovery request callback."""
    mock_callback = Mock()

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=[]),
        patch_scanned_serial_ports(return_value=[]),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_initial_scan_callback(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test it's possible to register a callback when the initial scan is done."""
    mock_callback_1 = Mock()
    mock_callback_2 = Mock()

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=[]),
        patch_scanned_serial_ports(return_value=[]),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_cancel_initial_scan_callback(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test it's possible to cancel an initial scan callback."""
    mock_callback = Mock()

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=[]),
        patch_scanned_serial_ports(return_value=[]),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_resolve_serial_by_id(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the discovery data resolves to serial/by-id."""
    new_usb = [{"domain": "test1", "vid": "3039", "pid": "3039"}]

    mock_ports = [
        USBDevice(
            device=slae_sh_device.device,
            vid="3039",
            pid="3039",
            serial_number=slae_sh_device.serial_number,
            manufacturer=slae_sh_device.manufacturer,
            description=slae_sh_device.description,
        )
    ]

    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=mock_ports),
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


@pytest.mark.usefixtures("force_usb_polling_watcher")
@pytest.mark.parametrize(
    "ports",
    [
        [
            USBDevice(
                device="/dev/cu.usbserial-2120",
                vid="3039",
                pid="3039",
                serial_number=conbee_device.serial_number,
                manufacturer=conbee_device.manufacturer,
                description=conbee_device.description,
            ),
            USBDevice(
                device="/dev/cu.usbserial-1120",
                vid="3039",
                pid="3039",
                serial_number=slae_sh_device.serial_number,
                manufacturer=slae_sh_device.manufacturer,
                description=slae_sh_device.description,
            ),
            USBDevice(
                device="/dev/cu.SLAB_USBtoUART",
                vid="3039",
                pid="3039",
                serial_number=conbee_device.serial_number,
                manufacturer=conbee_device.manufacturer,
                description=conbee_device.description,
            ),
            USBDevice(
                device="/dev/cu.SLAB_USBtoUART2",
                vid="3039",
                pid="3039",
                serial_number=slae_sh_device.serial_number,
                manufacturer=slae_sh_device.manufacturer,
                description=slae_sh_device.description,
            ),
        ],
        [
            USBDevice(
                device="/dev/cu.SLAB_USBtoUART2",
                vid="3039",
                pid="3039",
                serial_number=slae_sh_device.serial_number,
                manufacturer=slae_sh_device.manufacturer,
                description=slae_sh_device.description,
            ),
            USBDevice(
                device="/dev/cu.SLAB_USBtoUART",
                vid="3039",
                pid="3039",
                serial_number=conbee_device.serial_number,
                manufacturer=conbee_device.manufacturer,
                description=conbee_device.description,
            ),
            USBDevice(
                device="/dev/cu.usbserial-1120",
                vid="3039",
                pid="3039",
                serial_number=slae_sh_device.serial_number,
                manufacturer=slae_sh_device.manufacturer,
                description=slae_sh_device.description,
            ),
            USBDevice(
                device="/dev/cu.usbserial-2120",
                vid="3039",
                pid="3039",
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
        patch("homeassistant.components.usb.async_get_usb", return_value=new_usb),
        patch_scanned_serial_ports(return_value=ports),
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


@pytest.mark.parametrize(
    ("constant_name", "replacement_name", "replacement"),
    [
        (
            "UsbServiceInfo",
            "homeassistant.helpers.service_info.usb.UsbServiceInfo",
            UsbServiceInfo,
        ),
    ],
)
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    constant_name: str,
    replacement_name: str,
    replacement: Any,
) -> None:
    """Test deprecated automation constants."""
    import_and_test_deprecated_constant(
        caplog,
        usb,
        constant_name,
        replacement_name,
        replacement,
        "2026.2",
    )


@pytest.mark.usefixtures("force_usb_polling_watcher")
@patch("homeassistant.components.usb.REQUEST_SCAN_COOLDOWN", 0)
async def test_register_port_event_callback(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the registration of a port event callback."""

    port1 = USBDevice(
        device=slae_sh_device.device,
        vid="3039",
        pid="3039",
        serial_number=slae_sh_device.serial_number,
        manufacturer=slae_sh_device.manufacturer,
        description=slae_sh_device.description,
    )

    port2 = USBDevice(
        device=conbee_device.device,
        vid="303A",
        pid="303A",
        serial_number=conbee_device.serial_number,
        manufacturer=conbee_device.manufacturer,
        description=conbee_device.description,
    )

    ws_client = await hass_ws_client(hass)

    mock_callback1 = Mock()
    mock_callback2 = Mock()

    # Start off with no ports
    with (
        patch_scanned_serial_ports(return_value=[]),
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})

        _cancel1 = usb.async_register_port_event_callback(hass, mock_callback1)
        cancel2 = usb.async_register_port_event_callback(hass, mock_callback2)

    assert mock_callback1.mock_calls == []
    assert mock_callback2.mock_calls == []

    # Add two new ports
    with patch_scanned_serial_ports(return_value=[port1, port2]):
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]

    assert mock_callback1.mock_calls == [call({port1, port2}, set())]
    assert mock_callback2.mock_calls == [call({port1, port2}, set())]

    # Cancel the second callback
    cancel2()
    cancel2()

    mock_callback1.reset_mock()
    mock_callback2.reset_mock()

    # Remove port 2
    with patch_scanned_serial_ports(return_value=[port1]):
        await ws_client.send_json({"id": 2, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert mock_callback1.mock_calls == [call(set(), {port2})]
    assert mock_callback2.mock_calls == []  # The second callback was unregistered

    mock_callback1.reset_mock()
    mock_callback2.reset_mock()

    # Keep port 2 removed
    with patch_scanned_serial_ports(return_value=[port1]):
        await ws_client.send_json({"id": 3, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    # Nothing changed so no callback is called
    assert mock_callback1.mock_calls == []
    assert mock_callback2.mock_calls == []

    # Unplug one and plug in the other
    with patch_scanned_serial_ports(return_value=[port2]):
        await ws_client.send_json({"id": 4, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    assert mock_callback1.mock_calls == [call({port2}, {port1})]
    assert mock_callback2.mock_calls == []


@pytest.mark.usefixtures("force_usb_polling_watcher")
@patch("homeassistant.components.usb.REQUEST_SCAN_COOLDOWN", 0)
async def test_register_port_event_callback_failure(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test port event callback failure handling."""

    port1 = USBDevice(
        device=slae_sh_device.device,
        vid="3039",
        pid="3039",
        serial_number=slae_sh_device.serial_number,
        manufacturer=slae_sh_device.manufacturer,
        description=slae_sh_device.description,
    )

    port2 = USBDevice(
        device=conbee_device.device,
        vid="303A",
        pid="303A",
        serial_number=conbee_device.serial_number,
        manufacturer=conbee_device.manufacturer,
        description=conbee_device.description,
    )

    ws_client = await hass_ws_client(hass)

    mock_callback1 = Mock(side_effect=RuntimeError("Failure 1"))
    mock_callback2 = Mock(side_effect=RuntimeError("Failure 2"))

    # Start off with no ports
    with (
        patch_scanned_serial_ports(return_value=[]),
    ):
        assert await async_setup_component(hass, "usb", {"usb": {}})

        usb.async_register_port_event_callback(hass, mock_callback1)
        usb.async_register_port_event_callback(hass, mock_callback2)

    assert mock_callback1.mock_calls == []
    assert mock_callback2.mock_calls == []

    # Add two new ports
    with (
        patch_scanned_serial_ports(return_value=[port1, port2]),
        caplog.at_level(logging.ERROR, logger="homeassistant.components.usb"),
    ):
        await ws_client.send_json({"id": 1, "type": "usb/scan"})
        response = await ws_client.receive_json()
        assert response["success"]
        await hass.async_block_till_done()

    # Both were called even though they raised exceptions
    assert mock_callback1.mock_calls == [call({port1, port2}, set())]
    assert mock_callback2.mock_calls == [call({port1, port2}, set())]

    assert caplog.text.count("Error in USB port event callback") == 2
    assert "Failure 1" in caplog.text
    assert "Failure 2" in caplog.text
