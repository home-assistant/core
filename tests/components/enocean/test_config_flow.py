"""Tests for EnOcean config flow."""

from unittest.mock import Mock, patch

import pytest
import serial

from homeassistant import config_entries
from homeassistant.components.enocean import dongle
from homeassistant.components.enocean.config_flow import EnOceanFlowHandler
from homeassistant.components.enocean.const import DOMAIN
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DONGLE_VALIDATE_PATH_METHOD = "homeassistant.components.enocean.dongle.validate_path"
DONGLE_DETECT_METHOD = "homeassistant.components.enocean.dongle.detect"


async def test_user_flow_cannot_create_multiple_instances(hass: HomeAssistant) -> None:
    """Test that the user flow aborts if an instance is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: "/already/configured/path"}
    )
    entry.add_to_hass(hass)

    with patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_flow_with_detected_dongle(hass: HomeAssistant) -> None:
    """Test the user flow with a detected EnOcean dongle."""
    FAKE_DONGLE_PATH = "/fake/dongle"

    with patch(DONGLE_DETECT_METHOD, Mock(return_value=[FAKE_DONGLE_PATH])):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "detect"
    devices = result["data_schema"].schema.get(CONF_DEVICE).config.get("options")
    assert FAKE_DONGLE_PATH in devices
    assert EnOceanFlowHandler.MANUAL_PATH_VALUE in devices


async def test_user_flow_with_no_detected_dongle(hass: HomeAssistant) -> None:
    """Test the user flow with a detected EnOcean dongle."""
    with patch(DONGLE_DETECT_METHOD, Mock(return_value=[])):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_detection_flow_with_valid_path(hass: HomeAssistant) -> None:
    """Test the detection flow with a valid path selected."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "detect"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == USER_PROVIDED_PATH


async def test_detection_flow_with_custom_path(hass: HomeAssistant) -> None:
    """Test the detection flow with custom path selected."""
    USER_PROVIDED_PATH = EnOceanFlowHandler.MANUAL_PATH_VALUE
    FAKE_DONGLE_PATH = "/fake/dongle"

    with (
        patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=True)),
        patch(DONGLE_DETECT_METHOD, Mock(return_value=[FAKE_DONGLE_PATH])),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "detect"},
            data={CONF_DEVICE: USER_PROVIDED_PATH},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_detection_flow_with_invalid_path(hass: HomeAssistant) -> None:
    """Test the detection flow with an invalid path selected."""
    USER_PROVIDED_PATH = "/invalid/path"
    FAKE_DONGLE_PATH = "/fake/dongle"

    with (
        patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=False)),
        patch(DONGLE_DETECT_METHOD, Mock(return_value=[FAKE_DONGLE_PATH])),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "detect"},
            data={CONF_DEVICE: USER_PROVIDED_PATH},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "detect"
    assert CONF_DEVICE in result["errors"]


async def test_manual_flow_with_valid_path(hass: HomeAssistant) -> None:
    """Test the manual flow with a valid path."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == USER_PROVIDED_PATH


async def test_manual_flow_with_invalid_path(hass: HomeAssistant) -> None:
    """Test the manual flow with an invalid path."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(
        DONGLE_VALIDATE_PATH_METHOD,
        Mock(return_value=False),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert CONF_DEVICE in result["errors"]


async def test_import_flow_with_valid_path(hass: HomeAssistant) -> None:
    """Test the import flow with a valid path."""
    DATA_TO_IMPORT = {CONF_DEVICE: "/valid/path/to/import"}

    with patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=DATA_TO_IMPORT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == DATA_TO_IMPORT[CONF_DEVICE]


async def test_import_flow_with_invalid_path(hass: HomeAssistant) -> None:
    """Test the import flow with an invalid path."""
    DATA_TO_IMPORT = {CONF_DEVICE: "/invalid/path/to/import"}

    with patch(
        DONGLE_VALIDATE_PATH_METHOD,
        Mock(return_value=False),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=DATA_TO_IMPORT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_dongle_path"


async def test_manual_flow_with_rfc2217_url(hass: HomeAssistant) -> None:
    """Test the manual flow with a valid RFC2217 network URL."""
    NETWORK_URL = "rfc2217://192.168.1.100:3333"

    with patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}, data={CONF_DEVICE: NETWORK_URL}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == NETWORK_URL


async def test_manual_flow_with_socket_url(hass: HomeAssistant) -> None:
    """Test the manual flow with a valid socket network URL."""
    NETWORK_URL = "socket://localhost:5000"

    with patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}, data={CONF_DEVICE: NETWORK_URL}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == NETWORK_URL


@pytest.mark.parametrize(
    "test_url",
    [
        "rfc2217://hostname:3333",
        "rfc2217://192.168.1.100:3333",
        "socket://localhost:5000",
        "socket://example.com:8080",
        "loop://",
        "spy://dev/ttyUSB0",
    ],
)
def test_validate_path_network_urls_valid(test_url: str) -> None:
    """Test validate_path with valid network URL formats."""
    # Mock serial.serial_for_url since validate_path now uses it for URLs
    with patch("serial.serial_for_url") as mock_serial:
        mock_conn = Mock()
        mock_serial.return_value = mock_conn
        result = dongle.validate_path(test_url)

    assert result is True
    mock_serial.assert_called_once_with(test_url, baudrate=57600, timeout=0.1)
    mock_conn.close.assert_called_once()


@pytest.mark.parametrize(
    "test_url",
    [
        "rfc2217://",  # Missing netloc
        "rfc2217:/hostname:3333",  # Missing second slash
        "socket://",  # Missing netloc
        "http://example.com",  # Unsupported scheme
        "ftp://example.com",  # Unsupported scheme
    ],
)
def test_validate_path_network_urls_invalid_format(test_url: str) -> None:
    """Test validate_path with invalid network URL formats."""
    result = dongle.validate_path(test_url)
    assert result is False


def test_validate_path_network_url_connection_failure() -> None:
    """Test validate_path with network URL that fails to connect."""
    with patch("serial.serial_for_url") as mock_serial:
        mock_serial.side_effect = serial.SerialException("Connection refused")
        result = dongle.validate_path("rfc2217://unreachable:3333")

    assert result is False


def test_validate_path_backward_compatibility_local_path() -> None:
    """Test validate_path still works with local device paths."""
    with patch(
        "homeassistant.components.enocean.dongle.SerialCommunicator"
    ) as mock_comm:
        mock_comm.return_value = Mock()
        result = dongle.validate_path("/dev/ttyUSB0")

    assert result is True
    mock_comm.assert_called_once_with(port="/dev/ttyUSB0")


def test_validate_path_local_path_does_not_exist() -> None:
    """Test validate_path with non-existent local device path."""
    with patch(
        "homeassistant.components.enocean.dongle.SerialCommunicator"
    ) as mock_comm:
        mock_comm.side_effect = serial.SerialException("Device not found")
        result = dongle.validate_path("/dev/nonexistent")

    assert result is False


def test_is_serial_url() -> None:
    """Test _is_serial_url helper function."""
    assert dongle._is_serial_url("rfc2217://host:port") is True
    assert dongle._is_serial_url("socket://host:port") is True
    assert dongle._is_serial_url("loop://") is True
    assert dongle._is_serial_url("spy://dev/tty") is True
    assert dongle._is_serial_url("/dev/ttyUSB0") is False
    assert dongle._is_serial_url("/dev/serial/by-id/usb-EnOcean") is False
    assert dongle._is_serial_url("http://example.com") is False
