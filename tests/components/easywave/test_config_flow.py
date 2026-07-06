"""Tests for the config flow of the Easywave Core integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.easywave.const import (
    CONF_DEVICE_PATH,
    CONF_USB_PID,
    CONF_USB_SERIAL_NUMBER,
    CONF_USB_VID,
    DOMAIN,
    SUBENTRY_TYPE_NEO_SENSOR,
    SUBENTRY_TYPE_TRANSMITTER,
)
from homeassistant.config_entries import SOURCE_USB, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

COMPORTS_PATH = (
    "homeassistant.components.easywave.config_flow.serial.tools.list_ports.comports"
)
TRANSCEIVER_PATH = "homeassistant.components.easywave.config_flow.RX11Transceiver"


def _patch_connecting_transceiver(*, connected: bool = True) -> patch:
    """Patch RX11Transceiver to simulate a successful or failed connection."""
    mock_transceiver = MagicMock()
    mock_transceiver.connect = AsyncMock(return_value=connected)
    mock_transceiver.dispose = AsyncMock()
    return patch(TRANSCEIVER_PATH, return_value=mock_transceiver)


def _make_port(
    device: str = "/dev/ttyACM0",
    vid: int = 0x155A,
    pid: int = 0x1014,
    serial_number: str = "12345",
    manufacturer: str = "ELDAT",
    product: str = "RX11 USB Transceiver",
) -> MagicMock:
    """Create a mock serial port object."""
    port = MagicMock()
    port.device = device
    port.vid = vid
    port.pid = pid
    port.serial_number = serial_number
    port.manufacturer = manufacturer
    port.product = product
    return port


async def test_user_flow_no_devices(hass: HomeAssistant) -> None:
    """Test user flow aborts when no serial ports are found."""
    with patch(COMPORTS_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_ignores_non_rx11_ports(hass: HomeAssistant) -> None:
    """Test user flow aborts when no RX11 stick is connected."""
    other_port = _make_port(
        device="/dev/ttyUSB0",
        vid=0x1234,
        pid=0x5678,
        manufacturer="Other",
        product="Other Device",
    )

    with patch(COMPORTS_PATH, return_value=[other_port]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_select_port(hass: HomeAssistant) -> None:
    """Test user flow shows port selection form and proceeds to confirm."""
    port = _make_port()

    with patch(COMPORTS_PATH, return_value=[port]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ports"

    with patch(COMPORTS_PATH, return_value=[port]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"


async def test_user_flow_aborts_when_frequency_not_permitted(
    hass: HomeAssistant,
) -> None:
    """Test user flow aborts when 868 MHz is not permitted in the configured country."""
    hass.config.country = "US"
    port = _make_port()

    with patch(COMPORTS_PATH, return_value=[port]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    with patch(COMPORTS_PATH, return_value=[port]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "frequency_not_permitted"


async def test_usb_discovery_aborts_when_frequency_not_permitted(
    hass: HomeAssistant,
    mock_usb_discovery_info: UsbServiceInfo,
) -> None:
    """Test USB discovery aborts when 868 MHz is not permitted in the configured country."""
    hass.config.country = "US"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=mock_usb_discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "frequency_not_permitted"


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """Test user flow creates entry after port selection and confirmation."""
    port = _make_port()

    with patch(COMPORTS_PATH, return_value=[port]), _patch_connecting_transceiver():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Easywave Gateway"
    assert result["data"][CONF_DEVICE_PATH] == "/dev/ttyACM0"
    assert result["data"][CONF_USB_VID] == 0x155A
    assert result["data"][CONF_USB_PID] == 0x1014
    assert result["data"][CONF_USB_SERIAL_NUMBER] == "12345"


async def test_user_flow_cannot_connect_on_confirm(hass: HomeAssistant) -> None:
    """Test confirm step shows an error when the RX11 cannot be reached."""
    port = _make_port()

    with (
        patch(COMPORTS_PATH, return_value=[port]),
        _patch_connecting_transceiver(connected=False),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_multiple_ports(hass: HomeAssistant) -> None:
    """Test user flow with multiple serial ports shows selection form."""
    port1 = _make_port()
    port2 = _make_port(device="/dev/ttyACM1", serial_number="54321")

    with patch(COMPORTS_PATH, return_value=[port1, port2]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ports"


async def test_user_flow_existing_gateway_shows_device_select(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow shows device selection when a gateway is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "device_select"
    assert set(result["menu_options"]) == {
        SUBENTRY_TYPE_TRANSMITTER,
        SUBENTRY_TYPE_NEO_SENSOR,
    }


async def test_user_flow_device_select_starts_transmitter_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test device selection continues with transmitter setup in the same flow."""
    mock_config_entry.add_to_hass(hass)
    mock_coordinator = MagicMock()
    mock_coordinator.transceiver.is_connected = True
    runtime_data = MagicMock()
    runtime_data.coordinator = mock_coordinator
    mock_config_entry.runtime_data = runtime_data

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "device_select"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": SUBENTRY_TYPE_TRANSMITTER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "transmitter_learn_intro"


async def test_user_flow_device_disappeared(hass: HomeAssistant) -> None:
    """Test user step shows error when selected device is no longer available."""
    port1 = _make_port()
    port2 = _make_port(device="/dev/ttyACM1", serial_number="54321")

    with patch(COMPORTS_PATH, return_value=[port1, port2]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ports"

    # On re-scan the selected port is gone
    port3 = _make_port(device="/dev/ttyACM2", serial_number="99999")
    with patch(COMPORTS_PATH, return_value=[port2, port3]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ports"
    assert result["errors"] == {"base": "device_no_longer_available"}


async def test_usb_discovery_flow(
    hass: HomeAssistant, mock_usb_discovery_info: UsbServiceInfo
) -> None:
    """Test USB auto-discovery shows confirm form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=mock_usb_discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"


async def test_usb_discovery_flow_creates_entry(
    hass: HomeAssistant, mock_usb_discovery_info: UsbServiceInfo
) -> None:
    """Test USB discovery creates entry after confirmation."""
    with _patch_connecting_transceiver():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USB},
            data=mock_usb_discovery_info,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Easywave Gateway"
    assert result["data"][CONF_USB_VID] == 0x155A
    assert result["data"][CONF_USB_PID] == 0x1014


async def test_usb_discovery_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_usb_discovery_info: UsbServiceInfo,
) -> None:
    """Test USB discovery aborts when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=mock_usb_discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_confirm_unique_id_from_vid_pid(hass: HomeAssistant) -> None:
    """Test unique_id falls back to VID/PID when serial is unknown."""
    port = _make_port(serial_number="unknown")

    with patch(COMPORTS_PATH, return_value=[port]), _patch_connecting_transceiver():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"},
        )

        assert result["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "easywave_155A_1014"
