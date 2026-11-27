"""Tests for EnOcean config flow."""

from unittest.mock import AsyncMock, patch

from enocean_async import SerialProtocol
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.enocean.config_flow import EnOceanFlowHandler
from homeassistant.components.enocean.const import CONF_PROTOCOL, DOMAIN, MANUFACTURER
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

DETECT_METHOD = "homeassistant.components.enocean.config_flow.detect_serial_protocol"
GLOB_METHOD = "homeassistant.components.enocean.config_flow.glob.glob"
SETUP_ENTRY_METHOD = "homeassistant.components.enocean.async_setup_entry"


async def test_user_flow_cannot_create_multiple_instances(hass: HomeAssistant) -> None:
    """Test that the user flow aborts if an instance is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: "/already/configured/path"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_flow_with_detected_dongle(hass: HomeAssistant) -> None:
    """Test the user flow with a detected EnOcean dongle."""
    FAKE_DONGLE_PATH = "/fake/dongle"

    with (
        patch(GLOB_METHOD, side_effect=[[FAKE_DONGLE_PATH], [], []]),
        patch(DETECT_METHOD, return_value=SerialProtocol.ESP3),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "detect"
    devices = result["data_schema"].schema.get(CONF_DEVICE).config.get("options")
    assert FAKE_DONGLE_PATH in devices
    assert EnOceanFlowHandler.MANUAL_PATH_VALUE in devices


@pytest.mark.parametrize(
    ("found_paths", "expected_devices", "expected_probed_paths"),
    [
        pytest.param(
            [[], ["/fake/silent/port", "/fake/dongle"], []],
            ["/fake/dongle"],
            {"/fake/silent/port", "/fake/dongle"},
            id="port_without_dongle_is_hidden",
        ),
        pytest.param(
            [[], [], ["/dev/tty.usbserial-1234"]],
            ["/dev/tty.usbserial-1234"],
            set(),
            id="generic_serial_port_is_listed_without_probing",
        ),
    ],
)
async def test_user_flow_lists_answering_dongles(
    hass: HomeAssistant,
    found_paths: list[list[str]],
    expected_devices: list[str],
    expected_probed_paths: set[str],
) -> None:
    """Test that the user flow only probes and lists the right ports."""

    async def detect(port: str) -> SerialProtocol | None:
        return SerialProtocol.ESP2 if port == "/fake/dongle" else None

    with (
        patch(GLOB_METHOD, side_effect=found_paths),
        patch(DETECT_METHOD, side_effect=detect) as detect_mock,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "detect"
    devices = result["data_schema"].schema.get(CONF_DEVICE).config.get("options")
    assert devices == [*expected_devices, EnOceanFlowHandler.MANUAL_PATH_VALUE]
    probed_paths = {detect_call.args[0] for detect_call in detect_mock.call_args_list}
    assert probed_paths == expected_probed_paths


async def test_user_flow_with_no_answering_dongle(hass: HomeAssistant) -> None:
    """Test the user flow when no dongle answers on the detected ports."""
    with (
        patch(GLOB_METHOD, side_effect=[["/fake/silent/port"], [], []]),
        patch(DETECT_METHOD, return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_user_flow_with_no_detected_dongle(hass: HomeAssistant) -> None:
    """Test the user flow with no detected EnOcean dongle."""
    with patch(GLOB_METHOD, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_detection_flow_with_valid_path(hass: HomeAssistant) -> None:
    """Test the detection flow with a valid path selected."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(DETECT_METHOD, return_value=SerialProtocol.ESP3):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "detect"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == USER_PROVIDED_PATH


async def test_detection_flow_with_custom_path(hass: HomeAssistant) -> None:
    """Test the detection flow with custom path selected."""
    USER_PROVIDED_PATH = EnOceanFlowHandler.MANUAL_PATH_VALUE

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

    with patch(DETECT_METHOD, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "detect"},
            data={CONF_DEVICE: USER_PROVIDED_PATH},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert CONF_DEVICE in result["errors"]

    with (
        patch(DETECT_METHOD, return_value=SerialProtocol.ESP3),
        patch(SETUP_ENTRY_METHOD, AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: USER_PROVIDED_PATH}
        )

    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_flow_with_valid_path(hass: HomeAssistant) -> None:
    """Test the manual flow with a valid path."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(DETECT_METHOD, return_value=SerialProtocol.ESP3):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == USER_PROVIDED_PATH


@pytest.mark.parametrize(
    ("protocol", "expected_protocol"),
    [
        pytest.param(SerialProtocol.ESP3, "esp3", id="esp3_dongle"),
        pytest.param(SerialProtocol.ESP2, "esp2", id="esp2_dongle"),
    ],
)
async def test_manual_flow_stores_the_detected_protocol(
    hass: HomeAssistant, protocol: SerialProtocol, expected_protocol: str
) -> None:
    """Test that the flow stores the serial protocol of the dongle."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with (
        patch(DETECT_METHOD, return_value=protocol) as detect_mock,
        patch(SETUP_ENTRY_METHOD, AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_DEVICE: USER_PROVIDED_PATH,
        CONF_PROTOCOL: expected_protocol,
    }
    detect_mock.assert_awaited_once_with(USER_PROVIDED_PATH)


async def test_manual_flow_with_invalid_path(hass: HomeAssistant) -> None:
    """Test the manual flow with an invalid path."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(DETECT_METHOD, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert CONF_DEVICE in result["errors"]

    with (
        patch(DETECT_METHOD, return_value=SerialProtocol.ESP3),
        patch(SETUP_ENTRY_METHOD, AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: USER_PROVIDED_PATH}
        )

    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_import_flow_with_valid_path(hass: HomeAssistant) -> None:
    """Test the import flow with a valid path."""
    DATA_TO_IMPORT = {CONF_DEVICE: "/valid/path/to/import"}

    with patch(DETECT_METHOD, return_value=SerialProtocol.ESP3):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=DATA_TO_IMPORT,
        )

    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == DATA_TO_IMPORT[CONF_DEVICE]


async def test_import_flow_with_invalid_path(hass: HomeAssistant) -> None:
    """Test the import flow with an invalid path."""
    DATA_TO_IMPORT = {CONF_DEVICE: "/invalid/path/to/import"}

    with patch(DETECT_METHOD, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=DATA_TO_IMPORT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_dongle_path"


async def test_usb_discovery(
    hass: HomeAssistant,
) -> None:
    """Test usb discovery success path."""
    usb_discovery_info = UsbServiceInfo(
        device="/dev/enocean0",
        pid="6001",
        vid="0403",
        serial_number="1234",
        description="USB 300",
        manufacturer="EnOcean GmbH",
    )
    device = "/dev/enocean0"
    # test discovery step
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=usb_discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"
    assert result["errors"] is None

    # test device path
    with (
        patch(DETECT_METHOD, return_value=SerialProtocol.ESP3),
        patch(SETUP_ENTRY_METHOD, AsyncMock(return_value=None)),
        patch(
            "homeassistant.components.usb.get_serial_by_id",
            side_effect=lambda x: x,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MANUFACTURER
    assert result["data"] == {"device": device, "protocol": "esp3"}
    assert result["context"]["unique_id"] == "0403:6001_1234_EnOcean GmbH_USB 300"
    assert result["context"]["title_placeholders"] == {
        "name": "USB 300 - /dev/enocean0, s/n: 1234 - EnOcean GmbH - 0403:6001"
    }
    assert result["result"].state is ConfigEntryState.LOADED


async def test_usb_discovery_already_configured_updates_path(
    hass: HomeAssistant,
) -> None:
    """Test usb discovery aborts when already configured and updates device path."""
    # Existing entry with the same unique_id but an old device path
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/enocean-old"},
        unique_id="0403:6001_1234_EnOcean GmbH_USB 300",
    )
    existing_entry.add_to_hass(hass)

    # New USB discovery for the same dongle but with an updated device path
    usb_discovery_info = UsbServiceInfo(
        device="/dev/enocean-new",
        pid="6001",
        vid="0403",
        serial_number="1234",
        description="USB 300",
        manufacturer="EnOcean GmbH",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=usb_discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
