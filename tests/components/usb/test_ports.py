"""Test USB utils."""

from unittest.mock import Mock, patch

from serial.tools.list_ports_common import ListPortInfo

from homeassistant.components.usb import async_get_usb_ports, get_usb_ports
from homeassistant.core import HomeAssistant


async def test_get_usb_ports_with_vid_pid() -> None:
    """Test get_usb_ports with VID/PID information."""
    mock_port = Mock()
    mock_port.device = "/dev/ttyUSB0"
    mock_port.serial_number = "12345"
    mock_port.manufacturer = "Test"
    mock_port.description = "Valid Device"
    mock_port.vid = 0x1234
    mock_port.pid = 0x5678

    mock_usb_device = Mock()
    mock_usb_device.vid = "1234"
    mock_usb_device.pid = "5678"

    with (
        patch("serial.tools.list_ports.comports", return_value=[mock_port]),
        patch(
            "homeassistant.components.usb.get_serial_by_id",
            return_value="/dev/ttyUSB0",
        ),
        patch(
            "homeassistant.components.usb.utils.usb_device_from_port",
            return_value=mock_usb_device,
        ),
        patch(
            "homeassistant.components.usb.human_readable_device_name",
            return_value="Valid Device",
        ),
    ):
        result = get_usb_ports()
        assert result == {"/dev/ttyUSB0": "Valid Device"}


async def test_get_usb_ports_filtering_mixed_ports() -> None:
    """Test get_usb_ports filtering with mixed valid and 'n/a' ports."""
    mock_port1 = Mock()
    mock_port1.device = "/dev/ttyUSB0"
    mock_port1.serial_number = "12345"
    mock_port1.manufacturer = "Test"
    mock_port1.description = "Valid Device"
    mock_port1.vid = None
    mock_port1.pid = None

    mock_port2 = Mock()
    mock_port2.device = "/dev/ttyUSB1"
    mock_port2.serial_number = "67890"
    mock_port2.manufacturer = "Test"
    mock_port2.description = "n/a"
    mock_port2.vid = None
    mock_port2.pid = None

    with (
        patch(
            "serial.tools.list_ports.comports", return_value=[mock_port1, mock_port2]
        ),
        patch(
            "homeassistant.components.usb.get_serial_by_id",
            side_effect=["/dev/ttyUSB0", "/dev/ttyUSB1"],
        ),
        patch(
            "homeassistant.components.usb.human_readable_device_name",
            side_effect=["Valid Device", "n/a"],
        ),
    ):
        result = get_usb_ports()
        # Should filter out the "n/a" port and only return the valid one
        assert result == {"/dev/ttyUSB0": "Valid Device"}


async def test_get_usb_ports_filtering() -> None:
    """Test that get_usb_ports filters out 'n/a' descriptions when other ports are available."""

    mock_ports = [
        ListPortInfo("/dev/ttyUSB0"),
        ListPortInfo("/dev/ttyUSB1"),
        ListPortInfo("/dev/ttyUSB2"),
        ListPortInfo("/dev/ttyUSB3"),
    ]
    mock_ports[0].description = "n/a"
    mock_ports[1].description = "Device A"
    mock_ports[2].description = "N/A"
    mock_ports[3].description = "Device B"

    with patch("serial.tools.list_ports.comports", return_value=mock_ports):
        result = get_usb_ports()

        descriptions = list(result.values())

        # Verify that only non-"n/a" descriptions are returned
        assert descriptions == [
            "Device A - /dev/ttyUSB1, s/n: n/a",
            "Device B - /dev/ttyUSB3, s/n: n/a",
        ]


async def test_get_usb_ports_all_na() -> None:
    """Test that get_usb_ports returns all ports as-is when only 'n/a' descriptions exist."""

    mock_ports = [
        ListPortInfo("/dev/ttyUSB0"),
        ListPortInfo("/dev/ttyUSB1"),
        ListPortInfo("/dev/ttyUSB2"),
    ]
    mock_ports[0].description = "n/a"
    mock_ports[1].description = "N/A"
    mock_ports[2].description = "n/a"

    with patch("serial.tools.list_ports.comports", return_value=mock_ports):
        result = get_usb_ports()

        descriptions = list(result.values())

        # Verify that all ports are returned since they all have "n/a" descriptions
        assert len(descriptions) == 3
        # Verify that all descriptions contain "n/a" (case-insensitive)
        assert all("n/a" in desc.lower() for desc in descriptions)
        # Verify that all expected device paths are present
        device_paths = [desc.split(" - ")[1].split(",")[0] for desc in descriptions]
        assert "/dev/ttyUSB0" in device_paths
        assert "/dev/ttyUSB1" in device_paths
        assert "/dev/ttyUSB2" in device_paths


async def test_get_usb_ports_mixed_case_filtering() -> None:
    """Test that get_usb_ports filters out 'n/a' descriptions with different case variations."""

    mock_ports = [
        ListPortInfo("/dev/ttyUSB0"),
        ListPortInfo("/dev/ttyUSB1"),
        ListPortInfo("/dev/ttyUSB2"),
        ListPortInfo("/dev/ttyUSB3"),
    ]
    mock_ports[0].description = "n/a"
    mock_ports[1].description = "Not Available"
    mock_ports[2].description = "N/A"
    mock_ports[3].description = "Device B"

    with patch("serial.tools.list_ports.comports", return_value=mock_ports):
        result = get_usb_ports()

        descriptions = list(result.values())

        # Verify that only non-"n/a" descriptions are returned
        assert descriptions == [
            "Not Available - /dev/ttyUSB1, s/n: n/a",
            "Device B - /dev/ttyUSB3, s/n: n/a",
        ]


async def test_get_usb_ports_empty_list() -> None:
    """Test that get_usb_ports handles empty port list."""
    with patch("serial.tools.list_ports.comports", return_value=[]):
        result = get_usb_ports()
        assert result == {}


async def test_get_usb_ports_single_na_port() -> None:
    """Test that get_usb_ports returns single 'n/a' port when it's the only one available."""

    mock_port = ListPortInfo("/dev/ttyUSB0")
    mock_port.description = "n/a"

    with patch("serial.tools.list_ports.comports", return_value=[mock_port]):
        result = get_usb_ports()
        assert len(result) == 1
        assert "/dev/ttyUSB0" in result
        assert "n/a" in result["/dev/ttyUSB0"].lower()


async def test_get_usb_ports_single_valid_port() -> None:
    """Test that get_usb_ports returns single valid port."""

    mock_port = ListPortInfo("/dev/ttyUSB0")
    mock_port.description = "Valid Device"

    with patch("serial.tools.list_ports.comports", return_value=[mock_port]):
        result = get_usb_ports()
        assert len(result) == 1
        assert "/dev/ttyUSB0" in result
        assert "Valid Device" in result["/dev/ttyUSB0"]


async def test_async_get_usb_ports_exception_handling(hass: HomeAssistant) -> None:
    """Test async_get_usb_ports exception handling."""
    with (
        patch(
            "homeassistant.components.usb.get_usb_ports",
            side_effect=OSError("USB scan failed"),
        ),
        patch("homeassistant.components.usb._LOGGER.warning") as mock_logger,
    ):
        result = await async_get_usb_ports(hass)
        assert result == {}
        mock_logger.assert_called_once()
