"""Test Rainforest RAVEn config flow."""

from collections.abc import Generator
import socket
from unittest.mock import AsyncMock, Mock, patch

from aioraven.data import MeterList
from aioraven.device import RAVEnConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.rainforest_raven.config_flow import _format_id
from homeassistant.components.rainforest_raven.const import (
    CONF_NETWORK_ENDPOINT,
    DOMAIN,
    NETWORK_SOCKET_OPTION,
)
from homeassistant.components.usb import USBDevice
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_USB, SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_MAC, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import DeviceRegistry

from . import create_mock_device
from .const import DEVICE_INFO, DEVICE_NAME, DISCOVERY_INFO, METER_INFO, METER_LIST

UNIQUE_ID = "04B4:0003_1234_Rainforest Automation, Inc._RFA-Z105-2 HW2.7.3 EMU-2"
NETWORK_ENDPOINT = "socket://192.0.2.10:9999"
SOCKET_UNIQUE_ID = "socket_abcdef0123456789"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(None, "0000", id="none"),
        pytest.param(42, "002A", id="integer"),
    ],
)
def test_format_id(value: int | None, expected: str) -> None:
    """Test formatting numeric USB identifiers."""
    assert _format_id(value) == expected


@pytest.fixture
def mock_device() -> Generator[AsyncMock]:
    """Mock a functioning RAVEn device."""
    device = create_mock_device()
    with patch(
        "homeassistant.components.rainforest_raven.config_flow.RAVEnSerialDevice",
        return_value=device,
    ):
        yield device


@pytest.fixture
def mock_device_no_open(mock_device: AsyncMock) -> AsyncMock:
    """Mock a device which fails to open."""
    mock_device.__aenter__.side_effect = RAVEnConnectionError
    mock_device.open.side_effect = RAVEnConnectionError
    return mock_device


@pytest.fixture
def mock_device_comm_error(mock_device: AsyncMock) -> AsyncMock:
    """Mock a device which fails to read or parse raw data."""
    mock_device.get_meter_list.side_effect = RAVEnConnectionError
    mock_device.get_meter_info.side_effect = RAVEnConnectionError
    return mock_device


@pytest.fixture
def mock_device_timeout(mock_device: AsyncMock) -> AsyncMock:
    """Mock a device which times out when queried."""
    mock_device.get_meter_list.side_effect = TimeoutError
    mock_device.get_meter_info.side_effect = TimeoutError
    return mock_device


@pytest.fixture
def mock_comports() -> Generator[list[USBDevice]]:
    """Mock serial port list."""
    port = USBDevice(
        device=DISCOVERY_INFO.device,
        vid=f"{int(DISCOVERY_INFO.vid, 16):04X}",
        pid=f"{int(DISCOVERY_INFO.pid, 16):04X}",
        serial_number=DISCOVERY_INFO.serial_number,
        manufacturer=DISCOVERY_INFO.manufacturer,
        description=DISCOVERY_INFO.description,
    )
    comports = [port]
    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        return_value=comports,
    ):
        yield comports


async def _async_finish_flow(hass: HomeAssistant, flow_id: str) -> None:
    """Finish the user flow by selecting the device and the first meter."""
    with patch(
        "homeassistant.components.rainforest_raven.async_setup_entry",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, user_input={CONF_DEVICE: DEVICE_NAME}
        )
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "meters"

        result = await hass.config_entries.flow.async_configure(
            flow_id, user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]}
        )
    assert result.get("type") is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_comports", "mock_device")
async def test_flow_usb(hass: HomeAssistant) -> None:
    """Test usb flow connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USB}, data=DISCOVERY_INFO
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")
    assert result.get("flow_id")
    assert result.get("step_id") == "meters"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]}
    )
    assert result
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UNIQUE_ID


@pytest.mark.usefixtures("mock_device")
async def test_flow_usb_duplicate_device(
    hass: HomeAssistant, device_registry: DeviceRegistry
) -> None:
    """Test USB setup rejects a device already configured over another transport."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: NETWORK_ENDPOINT, CONF_MAC: []},
        unique_id="socket-entry",
    )
    existing_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=existing_entry.entry_id,
        identifiers={(DOMAIN, DEVICE_INFO.device_mac_id.hex())},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USB}, data=DISCOVERY_INFO
    )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "device_already_configured"


@pytest.mark.usefixtures("mock_device")
async def test_flow_usb_duplicate_socket_entry_without_registry(
    hass: HomeAssistant,
) -> None:
    """Test USB setup rejects a socket entry without a device registry record."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: NETWORK_ENDPOINT, CONF_MAC: []},
        unique_id=SOCKET_UNIQUE_ID,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USB}, data=DISCOVERY_INFO
    )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "device_already_configured"


@pytest.mark.usefixtures("mock_comports", "mock_device")
async def test_flow_user_usb_duplicate_device(
    hass: HomeAssistant, device_registry: DeviceRegistry
) -> None:
    """Test user USB setup rejects a device already configured over another transport."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: NETWORK_ENDPOINT, CONF_MAC: []},
        unique_id="socket-entry",
    )
    existing_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=existing_entry.entry_id,
        identifiers={(DOMAIN, DEVICE_INFO.device_mac_id.hex())},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
    )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "device_already_configured"


@pytest.mark.usefixtures("mock_comports", "mock_device_no_open")
async def test_flow_usb_cannot_connect(hass: HomeAssistant) -> None:
    """Test usb flow connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USB}, data=DISCOVERY_INFO
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


@pytest.mark.usefixtures("mock_comports", "mock_device_timeout")
async def test_flow_usb_timeout_connect(hass: HomeAssistant) -> None:
    """Test usb flow connection timeout."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USB}, data=DISCOVERY_INFO
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "timeout_connect"


@pytest.mark.usefixtures("mock_comports", "mock_device_comm_error")
async def test_flow_usb_comm_error(hass: HomeAssistant) -> None:
    """Test usb flow connection failure to communicate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USB}, data=DISCOVERY_INFO
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


@pytest.mark.usefixtures("mock_comports", "mock_device")
async def test_flow_user(hass: HomeAssistant) -> None:
    """Test user flow connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")
    assert result.get("flow_id")
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE: DEVICE_NAME,
        },
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")
    assert result.get("flow_id")
    assert result.get("step_id") == "meters"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]}
    )
    assert result
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UNIQUE_ID


@pytest.mark.usefixtures("mock_comports")
async def test_flow_user_no_available_devices(hass: HomeAssistant) -> None:
    """Test user flow offers a network endpoint without available USB devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: DISCOVERY_INFO.device},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"


@pytest.mark.usefixtures("mock_comports")
async def test_flow_user_in_progress(hass: HomeAssistant) -> None:
    """Test user flow with no available devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")
    assert result.get("flow_id")
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_in_progress"


@pytest.mark.usefixtures("mock_comports")
async def test_flow_user_cannot_connect(
    hass: HomeAssistant, mock_device_no_open: AsyncMock
) -> None:
    """Test user flow connection failure to communicate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={
            CONF_DEVICE: DEVICE_NAME,
        },
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {CONF_DEVICE: "cannot_connect"}

    mock_device_no_open.__aenter__.side_effect = None

    await _async_finish_flow(hass, result["flow_id"])


@pytest.mark.usefixtures("mock_comports")
async def test_flow_user_timeout_connect(
    hass: HomeAssistant, mock_device_timeout: AsyncMock
) -> None:
    """Test user flow connection failure to communicate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={
            CONF_DEVICE: DEVICE_NAME,
        },
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {CONF_DEVICE: "timeout_connect"}

    mock_device_timeout.get_meter_list.side_effect = None
    mock_device_timeout.get_meter_info.side_effect = lambda meter: METER_INFO[meter]

    await _async_finish_flow(hass, result["flow_id"])


@pytest.mark.usefixtures("mock_comports")
async def test_flow_user_comm_error(
    hass: HomeAssistant, mock_device_comm_error: AsyncMock
) -> None:
    """Test user flow connection failure to communicate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={
            CONF_DEVICE: DEVICE_NAME,
        },
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {CONF_DEVICE: "cannot_connect"}

    mock_device_comm_error.get_meter_list.side_effect = None
    mock_device_comm_error.get_meter_info.side_effect = lambda meter: METER_INFO[meter]

    await _async_finish_flow(hass, result["flow_id"])


@pytest.mark.usefixtures("mock_comports", "mock_device")
async def test_flow_reconfigure(hass: HomeAssistant) -> None:
    """Test reconfiguring a device and its selected meters."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/old", CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "meters"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]}
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert entry.data == {
        CONF_DEVICE: DISCOVERY_INFO.device,
        CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()],
    }
    assert entry.unique_id == UNIQUE_ID


@pytest.mark.usefixtures("mock_device")
async def test_flow_user_network_endpoint(hass: HomeAssistant) -> None:
    """Test configuring a device using a socket endpoint."""
    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION},
        )
        assert result
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "network"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT.upper()},
        )
        assert result
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "meters"

        with patch(
            "homeassistant.components.rainforest_raven.async_setup_entry",
            return_value=None,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]},
            )

    assert result
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["result"].data[CONF_DEVICE] == NETWORK_ENDPOINT
    assert result["result"].unique_id == SOCKET_UNIQUE_ID


@pytest.mark.usefixtures("mock_device")
async def test_flow_user_network_endpoint_duplicate_device_mac(
    hass: HomeAssistant,
) -> None:
    """Test different endpoints for the same RAVEn device share an ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "socket://raven.local:9999", CONF_MAC: []},
        unique_id=SOCKET_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION}
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT},
        )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "device_already_configured"


@pytest.mark.usefixtures("mock_device")
async def test_flow_user_network_endpoint_duplicate_usb_device(
    hass: HomeAssistant, device_registry: DeviceRegistry
) -> None:
    """Test a USB-configured RAVEn device cannot be added a second time over TCP."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: DISCOVERY_INFO.device, CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEVICE_INFO.device_mac_id.hex())},
    )

    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION}
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT},
        )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "device_already_configured"


@pytest.mark.usefixtures("mock_device")
async def test_flow_user_invalid_network_endpoint(hass: HomeAssistant) -> None:
    """Test an invalid socket endpoint is rejected."""
    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION},
        )
        assert result
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "network"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NETWORK_ENDPOINT: "http://192.0.2.10:9999"},
        )
        assert result
        assert result.get("type") is FlowResultType.FORM
        assert result.get("errors") == {
            CONF_NETWORK_ENDPOINT: "invalid_network_endpoint"
        }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NETWORK_ENDPOINT: "socket://192.0.2.10:invalid"},
        )
        assert result
        assert result.get("type") is FlowResultType.FORM
        assert result.get("errors") == {
            CONF_NETWORK_ENDPOINT: "invalid_network_endpoint"
        }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT}
        )
        assert result
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "meters"

        with patch(
            "homeassistant.components.rainforest_raven.async_setup_entry",
            return_value=None,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]},
            )

    assert result
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["result"].data[CONF_DEVICE] == NETWORK_ENDPOINT


@pytest.mark.usefixtures("mock_comports")
async def test_flow_user_network_endpoint_host_not_found(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test an unresolved socket host is reported as a connection error."""
    mock_device.__aenter__.side_effect = socket.gaierror(
        socket.EAI_NONAME, "Name or service not known"
    )
    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION}
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NETWORK_ENDPOINT: "socket://invalid-host.invalid:9999"},
        )
        assert result
        assert result.get("type") is FlowResultType.FORM
        assert result.get("errors") == {CONF_NETWORK_ENDPOINT: "cannot_connect"}

        mock_device.__aenter__.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT}
        )
        assert result
        assert result.get("step_id") == "meters"

        with patch(
            "homeassistant.components.rainforest_raven.async_setup_entry",
            return_value=None,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]},
            )

    assert result
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["result"].data[CONF_DEVICE] == NETWORK_ENDPOINT


@pytest.mark.usefixtures("mock_comports")
async def test_flow_user_network_endpoint_comm_error(
    hass: HomeAssistant, mock_device_comm_error: AsyncMock
) -> None:
    """Test a RAVEn communication error is shown in the network form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION}
    )
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT},
    )

    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {CONF_NETWORK_ENDPOINT: "cannot_connect"}

    mock_device_comm_error.get_meter_list.side_effect = None
    mock_device_comm_error.get_meter_info.side_effect = lambda meter: METER_INFO[meter]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT},
    )
    assert result
    assert result.get("step_id") == "meters"

    with patch(
        "homeassistant.components.rainforest_raven.async_setup_entry",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]},
        )

    assert result
    assert result.get("type") is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_comports")
async def test_flow_user_network_endpoint_retry_clears_meters(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test retrying a socket endpoint only offers its meters."""
    first_meter = METER_LIST.meter_mac_ids[0]
    second_meter = bytes.fromhex("0011223344556677")
    mock_device.get_device_info.side_effect = [None, DEVICE_INFO]
    mock_device.get_meter_list.side_effect = [
        MeterList(device_mac_id=DEVICE_INFO.device_mac_id, meter_mac_ids=[first_meter]),
        MeterList(
            device_mac_id=DEVICE_INFO.device_mac_id, meter_mac_ids=[second_meter]
        ),
    ]
    mock_device.get_meter_info.side_effect = lambda meter: METER_INFO[first_meter]

    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION}
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT},
        )
        assert result
        assert result.get("errors") == {CONF_NETWORK_ENDPOINT: "cannot_connect"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NETWORK_ENDPOINT: "SOCKET://192.0.2.11:9999"},
        )

    assert result
    assert result.get("step_id") == "meters"
    assert result["data_schema"].schema[CONF_MAC].config["options"] == [
        second_meter.hex()
    ]
    with patch(
        "homeassistant.components.rainforest_raven.async_setup_entry",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_MAC: [second_meter.hex()]}
        )

    assert result
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["result"].data[CONF_DEVICE] == "socket://192.0.2.11:9999"


@pytest.mark.usefixtures("mock_comports")
async def test_flow_user_network_endpoint_timeout(
    hass: HomeAssistant, mock_device_timeout: AsyncMock
) -> None:
    """Test a timeout is shown in the network form and can be retried."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION}
    )
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT},
    )

    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {CONF_NETWORK_ENDPOINT: "timeout_connect"}

    mock_device_timeout.get_meter_list.side_effect = None
    mock_device_timeout.get_meter_info.side_effect = lambda meter: METER_INFO[meter]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT},
    )
    assert result
    assert result.get("step_id") == "meters"

    with patch(
        "homeassistant.components.rainforest_raven.async_setup_entry",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]},
        )

    assert result
    assert result.get("type") is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_comports")
async def test_flow_user_network_endpoint_missing_device_mac(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test socket setup rejects a device that provides no MAC address."""
    mock_device.get_device_info.return_value = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION}
    )
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT},
    )

    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {CONF_NETWORK_ENDPOINT: "cannot_connect"}

    mock_device.get_device_info.return_value = DEVICE_INFO
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT},
    )
    assert result
    assert result.get("step_id") == "meters"

    with patch(
        "homeassistant.components.rainforest_raven.async_setup_entry",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]},
        )

    assert result
    assert result.get("type") is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_device")
async def test_flow_reconfigure_network_selected_by_default(
    hass: HomeAssistant,
) -> None:
    """Test a configured network endpoint is preselected during reconfigure."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: NETWORK_ENDPOINT, CONF_MAC: []},
        unique_id=SOCKET_UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        return_value=[],
    ):
        result = await entry.start_reconfigure_flow(hass)
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "network"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "meters"

        with patch(
            "homeassistant.components.rainforest_raven.async_setup_entry",
            return_value=None,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]},
            )
            await hass.async_block_till_done()

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert entry.data[CONF_DEVICE] == NETWORK_ENDPOINT


@pytest.mark.usefixtures("mock_device")
async def test_flow_reconfigure_network_endpoint(
    hass: HomeAssistant, device_registry: DeviceRegistry
) -> None:
    """Test reconfiguring an entry to use a socket endpoint."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/old", CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEVICE_INFO.device_mac_id.hex())},
    )
    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        return_value=[],
    ):
        result = await entry.start_reconfigure_flow(hass)
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION},
        )
        assert result
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "network"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT},
        )
        assert result
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "meters"

        with patch(
            "homeassistant.components.rainforest_raven.async_setup_entry",
            return_value=None,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]},
            )
            await hass.async_block_till_done()

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert entry.data[CONF_DEVICE] == NETWORK_ENDPOINT
    assert entry.unique_id == SOCKET_UNIQUE_ID


@pytest.mark.usefixtures("mock_device")
async def test_flow_reconfigure_network_rejects_different_device(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test reconfiguring a socket entry rejects a different RAVEn device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: NETWORK_ENDPOINT, CONF_MAC: []},
        unique_id=SOCKET_UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    mock_device.get_device_info.return_value = Mock(
        device_mac_id=bytes.fromhex("0011223344556677")
    )

    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        return_value=[],
    ):
        result = await entry.start_reconfigure_flow(hass)
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION}
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NETWORK_ENDPOINT: "SOCKET://192.0.2.11:9999"},
        )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "unique_id_mismatch"
    assert entry.unique_id == SOCKET_UNIQUE_ID
    assert entry.data[CONF_DEVICE] == NETWORK_ENDPOINT


@pytest.mark.usefixtures("mock_device")
async def test_flow_reconfigure_usb_to_network_rejects_different_device(
    hass: HomeAssistant, device_registry: DeviceRegistry, mock_device: AsyncMock
) -> None:
    """Test USB-to-socket migration rejects a different RAVEn device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: DISCOVERY_INFO.device, CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEVICE_INFO.device_mac_id.hex())},
    )
    mock_device.get_device_info.return_value = Mock(
        device_mac_id=bytes.fromhex("0011223344556677")
    )

    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        return_value=[],
    ):
        result = await entry.start_reconfigure_flow(hass)
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION}
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT},
        )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "unique_id_mismatch"
    assert entry.unique_id == UNIQUE_ID
    assert entry.data[CONF_DEVICE] == DISCOVERY_INFO.device


@pytest.mark.usefixtures("mock_device")
async def test_flow_reconfigure_usb_to_network_requires_registered_device_mac(
    hass: HomeAssistant,
) -> None:
    """Test USB-to-socket migration is rejected without the original device MAC."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: DISCOVERY_INFO.device, CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        return_value=[],
    ):
        result = await entry.start_reconfigure_flow(hass)
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION}
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT},
        )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "unique_id_mismatch"
    assert entry.unique_id == UNIQUE_ID
    assert entry.data[CONF_DEVICE] == DISCOVERY_INFO.device


@pytest.mark.usefixtures("mock_comports")
async def test_flow_reconfigure_socket_to_usb_rejects_different_device_without_registry(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test socket MAC identity is checked when its registry device is unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: NETWORK_ENDPOINT, CONF_MAC: []},
        unique_id=SOCKET_UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    mock_device.get_device_info.return_value = Mock(
        device_mac_id=bytes.fromhex("0011223344556677")
    )

    result = await entry.start_reconfigure_flow(hass)
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
    )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "unique_id_mismatch"
    assert entry.unique_id == SOCKET_UNIQUE_ID
    assert entry.data[CONF_DEVICE] == NETWORK_ENDPOINT


@pytest.mark.usefixtures("mock_device")
async def test_flow_reconfigure_network_duplicate_device_mac(
    hass: HomeAssistant, device_registry: DeviceRegistry
) -> None:
    """Test reconfiguration rejects another entry for the same RAVEn device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/old", CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEVICE_INFO.device_mac_id.hex())},
    )
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "socket://raven.local:9999", CONF_MAC: []},
        unique_id=SOCKET_UNIQUE_ID,
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        return_value=[],
    ):
        result = await entry.start_reconfigure_flow(hass)
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE: NETWORK_SOCKET_OPTION}
        )
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NETWORK_ENDPOINT: NETWORK_ENDPOINT},
        )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "device_already_configured"


@pytest.mark.usefixtures("mock_comports")
async def test_flow_reconfigure_serial_duplicate(hass: HomeAssistant) -> None:
    """Test reconfiguration rejects another entry with the selected USB ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/old", CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/other", CONF_MAC: []},
        unique_id=UNIQUE_ID,
    ).add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
    )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("mock_comports", "mock_device")
async def test_flow_reconfigure_serial_duplicate_device_mac(
    hass: HomeAssistant, device_registry: DeviceRegistry
) -> None:
    """Test serial reconfiguration rejects another entry linked to the same device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/old", CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: NETWORK_ENDPOINT, CONF_MAC: []},
        unique_id="other-entry",
    )
    other_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, DEVICE_INFO.device_mac_id.hex())},
    )

    result = await entry.start_reconfigure_flow(hass)
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
    )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "device_already_configured"


@pytest.mark.usefixtures("mock_comports", "mock_device")
async def test_flow_reconfigure_serial_duplicate_registered_device_mac(
    hass: HomeAssistant, device_registry: DeviceRegistry
) -> None:
    """Test serial reconfiguration rejects another entry for a registered device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/old", CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEVICE_INFO.device_mac_id.hex())},
    )
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: NETWORK_ENDPOINT, CONF_MAC: []},
        unique_id="other-entry",
    )
    other_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, DEVICE_INFO.device_mac_id.hex())},
    )

    result = await entry.start_reconfigure_flow(hass)
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
    )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "device_already_configured"


@pytest.mark.usefixtures("mock_comports")
async def test_flow_reconfigure_serial_missing_device_mac(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test serial reconfiguration retries when the target device has no MAC."""
    mock_device.get_device_info.return_value = None
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: NETWORK_ENDPOINT, CONF_MAC: []},
        unique_id=SOCKET_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
    )

    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"
    assert result.get("errors") == {CONF_DEVICE: "cannot_connect"}

    mock_device.get_device_info.return_value = DEVICE_INFO
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
    )
    assert result
    assert result.get("step_id") == "meters"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]}
    )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"


@pytest.mark.usefixtures("mock_comports")
async def test_flow_reconfigure_usb_without_registry_uses_unique_id(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test USB unique ID validates reconfiguration when no device MAC is stored."""
    mock_device.get_device_info.return_value = None
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/old", CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
    )

    assert result
    assert result.get("step_id") == "meters"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]}
    )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert entry.unique_id == UNIQUE_ID


@pytest.mark.usefixtures("mock_comports")
async def test_flow_reconfigure_usb_without_registry_rejects_different_unique_id(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test USB unique ID rejects a different device when no MAC is registered."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/old", CONF_MAC: []},
        unique_id="old-usb-device",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
    )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "unique_id_mismatch"
    assert entry.unique_id == "old-usb-device"


async def test_flow_reconfigure_serial_disappears(
    hass: HomeAssistant,
    mock_comports: list[USBDevice],
    mock_device: AsyncMock,
) -> None:
    """Test a disconnected serial device can be retried after refreshing the form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/old", CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.rainforest_raven.config_flow.usb.async_scan_serial_ports",
        side_effect=[mock_comports, [], mock_comports, mock_comports],
    ):
        result = await entry.start_reconfigure_flow(hass)
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
        )
        assert result
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "reconfigure"
        assert result.get("errors") == {CONF_DEVICE: "cannot_connect"}

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result
        assert result.get("step_id") == "reconfigure"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
        )
        assert result
        assert result.get("step_id") == "meters"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]},
        )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"


@pytest.mark.usefixtures("mock_comports")
@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        pytest.param(TimeoutError, "timeout_connect", id="timeout"),
        pytest.param(RAVEnConnectionError, "cannot_connect", id="communication"),
        pytest.param(OSError, "cannot_connect", id="os-error"),
    ],
)
async def test_flow_reconfigure_serial_error_recovery(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    error: type[Exception],
    expected_error: str,
) -> None:
    """Test serial reconfigure connection errors can be fixed and retried."""
    mock_device.get_meter_list.side_effect = error
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/old", CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {CONF_DEVICE: expected_error}

    mock_device.get_meter_list.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
    )
    assert result
    assert result.get("step_id") == "meters"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]}
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"


@pytest.mark.usefixtures("mock_comports")
async def test_flow_reconfigure_ignores_ignored_entries(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test reconfiguration replaces a matching ignored discovery entry."""
    ignored_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        source=SOURCE_IGNORE,
        unique_id=UNIQUE_ID,
    )
    ignored_entry.add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/old", CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
    )
    assert result
    assert result.get("step_id") == "meters"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]}
    )

    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert hass.config_entries.async_get_entry(ignored_entry.entry_id) is None
    assert entry.unique_id == UNIQUE_ID


@pytest.mark.usefixtures("mock_comports")
async def test_flow_reconfigure_pauses_coordinator_updates(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test reconfiguration closes the active transport during validation."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: DISCOVERY_INFO.device, CONF_MAC: []},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.rainforest_raven.coordinator.RAVEnSerialDevice",
        return_value=mock_device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        result = await entry.start_reconfigure_flow(hass)
        assert result
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE: DEVICE_NAME}
        )

    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "meters"
    mock_device.close.assert_awaited_once()
