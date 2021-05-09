"""Tests for the Crownstone integration."""
from unittest.mock import AsyncMock, MagicMock, patch

from crownstone_cloud.exceptions import (
    CrownstoneAuthenticationError,
    CrownstoneUnknownError,
)
import pytest
from serial.tools.list_ports_common import ListPortInfo

from homeassistant import data_entry_flow
from homeassistant.components.crownstone.const import (
    CONF_USB,
    CONF_USB_PATH,
    CONF_USE_CROWNSTONE_USB,
    DOMAIN,
)
from homeassistant.const import CONF_EMAIL, CONF_ID, CONF_PASSWORD, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="crownstone_setup", autouse=True)
def crownstone_setup():
    """Mock Crownstone entry setup."""
    with patch(
        "homeassistant.components.crownstone.async_setup_entry", return_value=True
    ):
        yield


def get_mocked_crownstone_cloud():
    """Return a mocked Crownstone Cloud instance."""
    mock_cloud = MagicMock()
    mock_cloud.async_initialize = AsyncMock()

    return mock_cloud


def get_mocked_com_port():
    """Mock of a serial port."""
    port = ListPortInfo("/dev/ttyUSB1234")
    port.serial_number = "1234"
    port.manufacturer = "Crownstone"
    port.device = "/dev/ttyUSB1234"
    port.description = "Crownstone USB"

    return port


def create_mocked_entry_conf(unique_id: str, email: str, password: str, usb_path: str):
    """Set a result for the entry for comparison."""
    MOCK_CONF = {}
    MOCK_CONF[CONF_ID] = unique_id
    MOCK_CONF[CONF_EMAIL] = email
    MOCK_CONF[CONF_PASSWORD] = password
    MOCK_CONF[CONF_USB_PATH] = usb_path

    return MOCK_CONF


async def start_user_flow(hass: HomeAssistant, mocked_cloud: MagicMock):
    """Patch Crownstone Cloud and start the flow."""
    # mock login
    mocked_login_input = {
        CONF_EMAIL: "example@homeassistant.com",
        CONF_PASSWORD: "homeassistantisawesome",
    }

    with patch(
        "homeassistant.components.crownstone.config_flow.CrownstoneCloud",
        return_value=mocked_cloud,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=mocked_login_input
        )

    return result


async def test_no_user_input(hass: HomeAssistant):
    """Test the flow done in the correct way."""
    # test if a form is returned if no input is provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    # show the login form
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_abort_if_configured(hass: HomeAssistant):
    """Test flow with correct login input and abort if sphere already configured."""
    # create mock entry conf
    configured_entry = create_mocked_entry_conf(
        unique_id="example@homeassistant.com",
        email="example@homeassistant.com",
        password="homeassistantisawesome",
        usb_path="/dev/serial/by-id/crownstone-usb",
    )

    # create mocked entry
    MockConfigEntry(
        domain=DOMAIN,
        data=configured_entry,
        unique_id=configured_entry[CONF_ID],
    ).add_to_hass(hass)

    result = await start_user_flow(hass, get_mocked_crownstone_cloud())

    # test if we abort if we try to configure the same entry
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_authentication_errors(hass: HomeAssistant):
    """Test flow with wrong auth errors."""
    cloud = get_mocked_crownstone_cloud()
    # side effect: auth error login failed
    cloud.async_initialize.side_effect = CrownstoneAuthenticationError(
        exception_type="LOGIN_FAILED"
    )

    result = await start_user_flow(hass, cloud)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # side effect: auth error account not verified
    cloud.async_initialize.side_effect = CrownstoneAuthenticationError(
        exception_type="LOGIN_FAILED_EMAIL_NOT_VERIFIED"
    )

    result = await start_user_flow(hass, cloud)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "account_not_verified"}


async def test_unknown_error(hass: HomeAssistant):
    """Test flow with unknown error."""
    cloud = get_mocked_crownstone_cloud()
    # side effect: unknown error
    cloud.async_initialize.side_effect = CrownstoneUnknownError

    result = await start_user_flow(hass, cloud)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown_error"}


async def test_successful_login_no_usb(hass: HomeAssistant):
    """Test a successful login without configuring a USB."""
    entry_without_usb = create_mocked_entry_conf(
        unique_id="example@homeassistant.com",
        email="example@homeassistant.com",
        password="homeassistantisawesome",
        usb_path=None,
    )
    result = await start_user_flow(hass, get_mocked_crownstone_cloud())
    # should show usb form
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "usb"

    # don't setup USB dongle, create entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB: False}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == entry_without_usb


@patch(
    "serial.tools.list_ports.comports", MagicMock(return_value=[get_mocked_com_port()])
)
@patch(
    "homeassistant.components.crownstone.config_flow.get_serial_by_id",
    return_value="/dev/serial/by-id/crownstone-usb",
)
async def test_successful_login_with_usb(serial_mock: MagicMock, hass: HomeAssistant):
    """Test flow with correct login and usb configuration."""
    entry_with_usb = create_mocked_entry_conf(
        unique_id="example@homeassistant.com",
        email="example@homeassistant.com",
        password="homeassistantisawesome",
        usb_path="/dev/serial/by-id/crownstone-usb",
    )
    result = await start_user_flow(hass, get_mocked_crownstone_cloud())
    # should show usb form
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "usb"

    # should show usb config form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB: True}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "usb_config"

    # create a mocked port
    port = get_mocked_com_port()
    port_select = f"{port}" + f" - {port.manufacturer}"

    # select a port from the list
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: port_select}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == entry_with_usb
    assert serial_mock.call_count == 1


@patch(
    "serial.tools.list_ports.comports", MagicMock(return_value=[get_mocked_com_port()])
)
@patch(
    "homeassistant.components.crownstone.config_flow.get_serial_by_id",
    return_value="/dev/serial/by-id/crownstone-usb",
)
async def test_update_usb_config(serial_mock: MagicMock, hass: HomeAssistant):
    """Tests the update to the USB config triggered by options flow."""
    # create mock entry conf
    configured_entry = create_mocked_entry_conf(
        unique_id="example@homeassistant.com",
        email="example@homeassistant.com",
        password="homeassistantisawesome",
        usb_path=None,
    )

    # create mocked entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=configured_entry,
        unique_id=configured_entry[CONF_ID],
    )
    entry.add_to_hass(hass)

    # create a mocked port
    port = get_mocked_com_port()
    port_select = f"{port}" + f" - {port.manufacturer}"

    get = patch(
        "homeassistant.config_entries.ConfigEntries.async_get_entry", return_value=entry
    )
    reload = patch("homeassistant.config_entries.ConfigEntries.async_reload")

    # initialized from options flow callback
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "usb_config"},
        data={CONF_UNIQUE_ID: "example@homeassistant.com"},
    )

    with get as get_mock, reload as reload_mock:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_USB_PATH: port_select}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "usb_setup_successful"
        assert entry.data[CONF_USB_PATH] == "/dev/serial/by-id/crownstone-usb"
        assert get_mock.call_count == 1
        assert reload_mock.call_count == 1

    get_none = patch(
        "homeassistant.config_entries.ConfigEntries.async_get_entry", return_value=None
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "usb_config"},
        data={CONF_UNIQUE_ID: "example@homeassistant.com"},
    )

    with get_none as get_mock:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_USB_PATH: port_select}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "usb_setup_unsuccessful"


async def test_options_flow(hass: HomeAssistant):
    """Test options flow."""
    configured_entry = create_mocked_entry_conf(
        unique_id="example@homeassistant.com",
        email="example@homeassistant.com",
        password="homeassistantisawesome",
        usb_path=None,
    )

    # create mocked entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=configured_entry,
        unique_id=configured_entry[CONF_ID],
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    schema = result["data_schema"].schema
    for schema_key in schema:
        if schema_key == CONF_USE_CROWNSTONE_USB:
            # based on existence of a usb-path string
            assert not schema_key.default()

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_USE_CROWNSTONE_USB: True}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {CONF_USE_CROWNSTONE_USB: True}
