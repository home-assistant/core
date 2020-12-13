"""Test the Plugwise config flow."""
from unittest.mock import MagicMock, patch
import os

from plugwise.exceptions import (
    ConnectionFailedError,
    InvalidAuthentication,
    NetworkDown,
    PlugwiseException,
    StickInitError,
    TimeoutException,
)
import pytest
import serial.tools.list_ports
from voluptuous.error import MultipleInvalid

from homeassistant import setup
from homeassistant.components.plugwise.config_flow import (
    CONF_MANUAL_PATH,
    get_serial_by_id,
)
from homeassistant.components.plugwise.const import (
    CONF_USB_PATH,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FLOW_NET,
    FLOW_TYPE,
    FLOW_USB,
    PW_TYPE,
    STICK,
)
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SOURCE,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.async_mock import AsyncMock, MagicMock, patch, sentinel
from tests.common import MockConfigEntry

TEST_HOST = "1.1.1.1"
TEST_HOSTNAME = "smileabcdef"
TEST_PASSWORD = "test_password"
TEST_PORT = 81
TEST_USERNAME = "smile"
TEST_USERNAME2 = "stretch"
TEST_USBPORT = "/dev/ttyUSB1"
TEST_USBPORT2 = "/dev/ttyUSB2"

TEST_DISCOVERY = {
    "host": TEST_HOST,
    "port": DEFAULT_PORT,
    "hostname": f"{TEST_HOSTNAME}.local.",
    "server": f"{TEST_HOSTNAME}.local.",
    "properties": {
        "product": "smile",
        "version": "1.2.3",
        "hostname": f"{TEST_HOSTNAME}.local.",
    },
}


class FakeStick:
    """Mock class to emulate mac address fetching."""

    def get_mac_stick(mac="01:23:45:67:AB"):
        """Mock function returning a MAC address."""
        return mac


@pytest.fixture(name="mock_smile")
def mock_smile():
    """Create a Mock Smile for testing exceptions."""
    with patch(
        "homeassistant.components.plugwise.config_flow.Smile",
    ) as smile_mock:
        smile_mock.PlugwiseException = PlugwiseException
        smile_mock.InvalidAuthentication = InvalidAuthentication
        smile_mock.ConnectionFailedError = ConnectionFailedError
        smile_mock.return_value.connect.return_value = True
        yield smile_mock.return_value


def com_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo(TEST_USBPORT)
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.description = "Some serial port"
    return port


async def test_form_flow_gateway(hass):
    """Test we get the form for Plugwise Gateway product type."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={FLOW_TYPE: FLOW_NET}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user_gateway"


async def test_form_flow_usb(hass):
    """Test we get the form for Plugwise USB product type."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={FLOW_TYPE: FLOW_USB}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user_usb"


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_NET}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.plugwise.config_flow.Smile.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.plugwise.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.plugwise.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: DEFAULT_PORT,
        CONF_USERNAME: TEST_USERNAME,
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DISCOVERY,
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.plugwise.config_flow.Smile.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.plugwise.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.plugwise.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: DEFAULT_PORT,
        CONF_USERNAME: TEST_USERNAME,
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_username(hass):
    """Test we get the username data back."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_NET}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.plugwise.config_flow.Smile.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.plugwise.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.plugwise.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_USERNAME: TEST_USERNAME2,
            },
        )

    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: DEFAULT_PORT,
        CONF_USERNAME: TEST_USERNAME2,
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DISCOVERY,
    )
    assert result3["type"] == RESULT_TYPE_FORM
    assert result3["errors"] == {}

    with patch(
        "homeassistant.components.plugwise.config_flow.Smile.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.plugwise.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.plugwise.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            user_input={CONF_PASSWORD: TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert result4["type"] == "abort"
    assert result4["reason"] == "already_configured"


async def test_form_invalid_auth(hass, mock_smile):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_NET}
    )

    mock_smile.connect.side_effect = InvalidAuthentication
    mock_smile.gateway_id = "0a636a4fc1704ab4a24e4f7e37fb187a"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass, mock_smile):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_NET}
    )

    mock_smile.connect.side_effect = ConnectionFailedError
    mock_smile.gateway_id = "0a636a4fc1704ab4a24e4f7e37fb187a"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect_port(hass, mock_smile):
    """Test we handle cannot connect to port error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_NET}
    )

    mock_smile.connect.side_effect = ConnectionFailedError
    mock_smile.gateway_id = "0a636a4fc1704ab4a24e4f7e37fb187a"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: TEST_HOST,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
        },
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_other_problem(hass, mock_smile):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_NET}
    )

    mock_smile.connect.side_effect = TimeoutError
    mock_smile.gateway_id = "0a636a4fc1704ab4a24e4f7e37fb187a"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_options_flow_power(hass, mock_smile) -> None:
    """Test config flow options DSMR environments."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=CONF_NAME,
        data={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
        options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )

    hass.data[DOMAIN] = {entry.entry_id: {"api": MagicMock(smile_type="power")}}
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.plugwise.async_setup_entry", return_value=True
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_SCAN_INTERVAL: 10}
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {
            CONF_SCAN_INTERVAL: 10,
        }


async def test_options_flow_thermo(hass, mock_smile) -> None:
    """Test config flow options for thermostatic environments."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=CONF_NAME,
        data={CONF_HOST: TEST_HOST, CONF_PASSWORD: TEST_PASSWORD},
        options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )

    hass.data[DOMAIN] = {entry.entry_id: {"api": MagicMock(smile_type="thermostat")}}
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.plugwise.async_setup_entry", return_value=True
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_SCAN_INTERVAL: 60}
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {
            CONF_SCAN_INTERVAL: 60,
        }


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
@patch("plugwise.stick.connect", MagicMock(return_value=None))
@patch("plugwise.stick.initialize_stick", MagicMock(return_value=None))
@patch("plugwise.stick.disconnect", MagicMock(return_value=None))
async def test_user_flow_select(hass):
    """Test user flow when USB-stick is selected from list."""
    port = com_port()
    port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_USB}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: port_select}
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {PW_TYPE: STICK, CONF_USB_PATH: TEST_USBPORT}

    # Retry to ensure configuring the same port is not allowed
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_USB}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: port_select}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "already_configured"}


async def test_user_flow_manual_selected_show_form(hass):
    """Test user step form when manual path is selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_USB}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: CONF_MANUAL_PATH},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "manual_path"


@patch(
    "homeassistant.components.plugwise.config_flow.validate_usb_connection",
    AsyncMock(return_value=[None, FakeStick]),
)
async def test_user_flow_manual(hass):
    """Test user flow when USB-stick is manually entered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_USB}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: CONF_MANUAL_PATH},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: TEST_USBPORT2},
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {CONF_USB_PATH: TEST_USBPORT2}


async def test_invalid_connection(hass):
    """Test invalid connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_USB}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: CONF_MANUAL_PATH},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USB_PATH: "/dev/null"},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_empty_connection(hass):
    """Test empty connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={FLOW_TYPE: FLOW_USB}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: CONF_MANUAL_PATH},
    )

    try:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USB_PATH: None},
        )
        assert False
    except MultipleInvalid:
        assert True

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}


@patch("plugwise.stick.connect", MagicMock(return_value=None))
@patch("plugwise.stick.initialize_stick", MagicMock(side_effect=(StickInitError)))
async def test_failed_initialization(hass):
    """Test we handle failed initialization of Plugwise USB-stick."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={FLOW_TYPE: FLOW_USB},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: CONF_MANUAL_PATH},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: "/dev/null"},
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "stick_init"}


@patch("plugwise.stick.connect", MagicMock(return_value=None))
@patch("plugwise.stick.initialize_stick", MagicMock(side_effect=(NetworkDown)))
async def test_network_down_exception(hass):
    """Test we handle network_down exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={FLOW_TYPE: FLOW_USB},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: CONF_MANUAL_PATH},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: "/dev/null"},
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "network_down"}


@patch("plugwise.stick.connect", MagicMock(return_value=None))
@patch("plugwise.stick.initialize_stick", MagicMock(side_effect=(TimeoutException)))
async def test_timeout_exception(hass):
    """Test we handle time exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={FLOW_TYPE: FLOW_USB},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: CONF_MANUAL_PATH},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USB_PATH: "/dev/null"},
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "network_timeout"}


def test_get_serial_by_id_no_dir():
    """Test serial by id conversion if there's no /dev/serial/by-id."""
    p1 = patch("os.path.isdir", MagicMock(return_value=False))
    p2 = patch("os.scandir")
    with p1 as is_dir_mock, p2 as scan_mock:
        res = get_serial_by_id(sentinel.path)
        assert res is sentinel.path
        assert is_dir_mock.call_count == 1
        assert scan_mock.call_count == 0


def test_get_serial_by_id():
    """Test serial by id conversion."""
    p1 = patch("os.path.isdir", MagicMock(return_value=True))
    p2 = patch("os.scandir")

    def _realpath(path):
        if path is sentinel.matched_link:
            return sentinel.path
        return sentinel.serial_link_path

    p3 = patch("os.path.realpath", side_effect=_realpath)
    with p1 as is_dir_mock, p2 as scan_mock, p3:
        res = get_serial_by_id(sentinel.path)
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
        res = get_serial_by_id(sentinel.path)
        assert res is sentinel.matched_link
        assert is_dir_mock.call_count == 2
        assert scan_mock.call_count == 2
