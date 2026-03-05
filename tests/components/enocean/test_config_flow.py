"""Tests for EnOcean config flow."""

from unittest.mock import AsyncMock, Mock, patch

from serial import SerialException

from homeassistant.components.enocean.config_flow import EnOceanFlowHandler
from homeassistant.components.enocean.const import DOMAIN, MANUFACTURER
from homeassistant.components.usb import USBDevice
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_USB,
    SOURCE_USER,
    ConfigEntryState,
)
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from . import MOCK_SERIAL_BY_ID, MOCK_USB_DEVICE, MODULE

from tests.common import MockConfigEntry


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test that the user flow aborts if an instance is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: "/already/configured/path"}
    )
    entry.add_to_hass(hass)

    with patch(f"{MODULE}.dongle.validate_path", Mock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_flow_with_detected_usb_device(
    hass: HomeAssistant, mock_usb_device: USBDevice
) -> None:
    """Test the user flow with a detected usb device."""
    with patch(
        f"{MODULE}.config_flow.scan_serial_ports", Mock(return_value=[mock_usb_device])
    ) as mock_scan_serial_ports:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert mock_scan_serial_ports.call_count == 1
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    options = result["data_schema"].schema.get(CONF_DEVICE).config.get("options")
    assert len(options) == 2
    assert options[0].get("value") == "/dev/enocean0"
    assert options[1].get("value") == "manual"


async def test_user_flow_without_detected_usb_device(hass: HomeAssistant) -> None:
    """Test the user flow without detected usb device."""
    with patch(
        f"{MODULE}.config_flow.scan_serial_ports", Mock(return_value=[])
    ) as mock_scan_serial_ports:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert mock_scan_serial_ports.call_count == 1
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_user_flow_with_valid_path(
    hass: HomeAssistant, mock_usb_device: USBDevice
) -> None:
    """Test the user flow with a valid path selected."""
    with (
        patch(
            f"{MODULE}.config_flow.scan_serial_ports",
            Mock(return_value=[mock_usb_device]),
        ) as mock_scan_serial_ports,
        patch(
            f"{MODULE}.config_flow.get_serial_by_id",
            return_value=MOCK_SERIAL_BY_ID,
        ),
        patch(
            f"{MODULE}.dongle.validate_path",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_DEVICE: MOCK_USB_DEVICE.device},
        )

    assert mock_scan_serial_ports.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == MOCK_SERIAL_BY_ID
    assert result["context"]["unique_id"] == "0403:6001_1234_EnOcean GmbH_USB 300"


async def test_user_flow_with_invalid_manual_path(hass: HomeAssistant) -> None:
    """Test the user flow with custom path selected."""
    with (
        patch(
            f"{MODULE}.dongle.SerialCommunicator",
            side_effect=SerialException(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "manual"},
            data={CONF_DEVICE: "invalid/manual/path"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] is not None
    assert result["errors"][CONF_DEVICE] == "invalid_dongle_path"


async def test_user_flow_with_invalid_option(
    hass: HomeAssistant, mock_usb_device: USBDevice
) -> None:
    """Test the user flow with unknown selected usb device."""
    with patch(
        f"{MODULE}.config_flow.scan_serial_ports", Mock(return_value=[mock_usb_device])
    ) as mock_scan_serial_ports:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_DEVICE: "invalid/detected/path"},
        )

    assert mock_scan_serial_ports.call_count == 1
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown_device"


async def test_user_flow_with_manual_path(
    hass: HomeAssistant, mock_usb_device: USBDevice
) -> None:
    """Test the user flow with custom path selected."""
    with (
        patch(f"{MODULE}.dongle.validate_path", Mock(return_value=True)),
        patch(
            f"{MODULE}.config_flow.scan_serial_ports",
            Mock(return_value=[mock_usb_device]),
        ) as mock_scan_serial_ports,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_DEVICE: EnOceanFlowHandler.MANUAL_PATH_VALUE},
        )

    assert mock_scan_serial_ports.call_count == 1
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_user_flow_already_in_progress(
    hass: HomeAssistant,
    mock_usb_device: USBDevice,
    mock_usb_service_info: UsbServiceInfo,
) -> None:
    """Test we can't start a flow for the same device twice."""
    with patch(
        f"{MODULE}.config_flow.get_serial_by_id",
        return_value=MOCK_SERIAL_BY_ID,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USB},
            data=mock_usb_service_info,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"

    with (
        patch(f"{MODULE}.dongle.validate_path", Mock(return_value=True)),
        patch(
            f"{MODULE}.config_flow.scan_serial_ports",
            Mock(return_value=[mock_usb_device]),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_DEVICE: mock_usb_device.device},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_import_flow_with_valid_path(hass: HomeAssistant) -> None:
    """Test the import flow with a valid path."""
    DATA_TO_IMPORT = {CONF_DEVICE: "/valid/path/to/import"}

    with patch(f"{MODULE}.dongle.validate_path", Mock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=DATA_TO_IMPORT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == DATA_TO_IMPORT[CONF_DEVICE]


async def test_import_flow_with_invalid_path(hass: HomeAssistant) -> None:
    """Test the import flow with an invalid path."""
    DATA_TO_IMPORT = {CONF_DEVICE: "/invalid/path/to/import"}

    with patch(
        f"{MODULE}.dongle.validate_path",
        Mock(return_value=False),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=DATA_TO_IMPORT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_dongle_path"


async def test_usb_discovery(
    hass: HomeAssistant,
    mock_usb_service_info: UsbServiceInfo,
) -> None:
    """Test usb discovery success path."""
    # test discovery step
    with patch(
        f"{MODULE}.config_flow.get_serial_by_id",
        return_value=MOCK_SERIAL_BY_ID,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USB},
            data=mock_usb_service_info,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"
    assert result["errors"] is None
    assert result["description_placeholders"] == {
        "device": MOCK_SERIAL_BY_ID,
        "manufacturer": "EnOcean",
    }

    # test device path
    with (
        patch(f"{MODULE}.dongle.validate_path", Mock(return_value=True)),
        patch(f"{MODULE}.async_setup_entry", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MANUFACTURER
    assert result["data"] == {"device": MOCK_SERIAL_BY_ID}
    assert result["context"]["unique_id"] == "0403:6001_1234_EnOcean GmbH_USB 300"
    assert result["context"]["title_placeholders"] == {
        "name": "USB 300 - /dev/serial/by-id/enocean0, s/n: 1234 - EnOcean GmbH - 0403:6001"
    }
    assert result["result"].state is ConfigEntryState.LOADED


async def test_usb_discovery_already_configured(
    hass: HomeAssistant,
    mock_usb_service_info: UsbServiceInfo,
) -> None:
    """Test usb discovery aborts when already configured."""
    # Existing entry with the same unique_id but an old device path
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/enocean-old"},
        unique_id="0403:6001_1234_EnOcean GmbH_USB 300",
    )
    existing_entry.add_to_hass(hass)

    # New USB discovery for the same dongle but with an updated device path
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=mock_usb_service_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_usb_discovery_already_in_progress(
    hass: HomeAssistant, mock_usb_service_info: UsbServiceInfo
) -> None:
    """Test we can't start a flow for the same device twice."""
    with patch(
        f"{MODULE}.config_flow.get_serial_by_id",
        return_value=MOCK_SERIAL_BY_ID,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USB},
            data=mock_usb_service_info,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"

    with patch(
        f"{MODULE}.config_flow.get_serial_by_id",
        return_value=MOCK_SERIAL_BY_ID,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USB},
            data=mock_usb_service_info,
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
