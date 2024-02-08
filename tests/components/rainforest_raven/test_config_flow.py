"""Test Rainforest RAVEn config flow."""
from unittest.mock import patch

from aioraven.device import RAVEnConnectionError
import pytest
import serial.tools.list_ports

from homeassistant import data_entry_flow
from homeassistant.components.rainforest_raven.const import DOMAIN
from homeassistant.config_entries import SOURCE_USB, SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_MAC, CONF_SOURCE
from homeassistant.core import HomeAssistant

from . import create_mock_device
from .const import DEVICE_NAME, DISCOVERY_INFO, METER_LIST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_device():
    """Mock a functioning RAVEn device."""
    device = create_mock_device()
    with patch(
        "homeassistant.components.rainforest_raven.config_flow.RAVEnSerialDevice",
        return_value=device,
    ):
        yield device


@pytest.fixture
def mock_device_no_open(mock_device):
    """Mock a device which fails to open."""
    mock_device.__aenter__.side_effect = RAVEnConnectionError
    mock_device.open.side_effect = RAVEnConnectionError
    return mock_device


@pytest.fixture
def mock_device_comm_error(mock_device):
    """Mock a device which fails to read or parse raw data."""
    mock_device.get_meter_list.side_effect = RAVEnConnectionError
    mock_device.get_meter_info.side_effect = RAVEnConnectionError
    return mock_device


@pytest.fixture
def mock_device_timeout(mock_device):
    """Mock a device which times out when queried."""
    mock_device.get_meter_list.side_effect = TimeoutError
    mock_device.get_meter_info.side_effect = TimeoutError
    return mock_device


@pytest.fixture
def mock_comports():
    """Mock serial port list."""
    port = serial.tools.list_ports_common.ListPortInfo(DISCOVERY_INFO.device)
    port.serial_number = DISCOVERY_INFO.serial_number
    port.manufacturer = DISCOVERY_INFO.manufacturer
    port.device = DISCOVERY_INFO.device
    port.description = DISCOVERY_INFO.description
    port.pid = int(DISCOVERY_INFO.pid, 0)
    port.vid = int(DISCOVERY_INFO.vid, 0)
    comports = [port]
    with patch("serial.tools.list_ports.comports", return_value=comports):
        yield comports


async def test_flow_usb(hass: HomeAssistant, mock_comports, mock_device):
    """Test usb flow connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USB}, data=DISCOVERY_INFO
    )
    assert result
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert not result.get("errors")
    assert result.get("flow_id")
    assert result.get("step_id") == "meters"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]}
    )
    assert result
    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_flow_usb_cannot_connect(
    hass: HomeAssistant, mock_comports, mock_device_no_open
):
    """Test usb flow connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USB}, data=DISCOVERY_INFO
    )
    assert result
    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


async def test_flow_usb_timeout_connect(
    hass: HomeAssistant, mock_comports, mock_device_timeout
):
    """Test usb flow connection timeout."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USB}, data=DISCOVERY_INFO
    )
    assert result
    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "timeout_connect"


async def test_flow_usb_comm_error(
    hass: HomeAssistant, mock_comports, mock_device_comm_error
):
    """Test usb flow connection failure to communicate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USB}, data=DISCOVERY_INFO
    )
    assert result
    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


async def test_flow_user(hass: HomeAssistant, mock_comports, mock_device):
    """Test user flow connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    assert result
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
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
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert not result.get("errors")
    assert result.get("flow_id")
    assert result.get("step_id") == "meters"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MAC: [METER_LIST.meter_mac_ids[0].hex()]}
    )
    assert result
    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_flow_user_no_available_devices(hass: HomeAssistant, mock_comports):
    """Test user flow with no available devices."""
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
    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "no_devices_found"


async def test_flow_user_in_progress(hass: HomeAssistant, mock_comports):
    """Test user flow with no available devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    assert result
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert not result.get("errors")
    assert result.get("flow_id")
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    assert result
    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "already_in_progress"


async def test_flow_user_cannot_connect(
    hass: HomeAssistant, mock_comports, mock_device_no_open
):
    """Test user flow connection failure to communicate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={
            CONF_DEVICE: DEVICE_NAME,
        },
    )
    assert result
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {CONF_DEVICE: "cannot_connect"}


async def test_flow_user_timeout_connect(
    hass: HomeAssistant, mock_comports, mock_device_timeout
):
    """Test user flow connection failure to communicate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={
            CONF_DEVICE: DEVICE_NAME,
        },
    )
    assert result
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {CONF_DEVICE: "timeout_connect"}


async def test_flow_user_comm_error(
    hass: HomeAssistant, mock_comports, mock_device_comm_error
):
    """Test user flow connection failure to communicate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={
            CONF_DEVICE: DEVICE_NAME,
        },
    )
    assert result
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {CONF_DEVICE: "cannot_connect"}
