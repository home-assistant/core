"""Tests for the Crownstone integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from crownstone_cloud.cloud_models.spheres import Spheres
from crownstone_cloud.exceptions import (
    CrownstoneAuthenticationError,
    CrownstoneUnknownError,
)
import pytest
from serial.tools.list_ports_common import ListPortInfo

from homeassistant import data_entry_flow
from homeassistant.components import usb
from homeassistant.components.crownstone.const import (
    CONF_USB_MANUAL_PATH,
    CONF_USB_PATH,
    CONF_USB_SPHERE,
    CONF_USB_SPHERE_OPTION,
    CONF_USE_USB_OPTION,
    DOMAIN,
    DONT_USE_USB,
    MANUAL_PATH,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="crownstone_setup", autouse=True)
def crownstone_setup():
    """Mock Crownstone entry setup."""
    with patch(
        "homeassistant.components.crownstone.async_setup_entry", return_value=True
    ):
        yield


def get_mocked_crownstone_cloud(spheres: dict[str, MagicMock] | None = None):
    """Return a mocked Crownstone Cloud instance."""
    mock_cloud = MagicMock()
    mock_cloud.async_initialize = AsyncMock()
    mock_cloud.cloud_data = Spheres(MagicMock(), "account_id")
    mock_cloud.cloud_data.spheres = spheres

    return mock_cloud


def create_mocked_spheres(amount: int) -> dict[str, MagicMock]:
    """Return a dict with mocked sphere instances."""
    spheres: dict[str, MagicMock] = {}
    for i in range(amount):
        spheres[f"sphere_id_{i}"] = MagicMock()
        spheres[f"sphere_id_{i}"].name = f"sphere_name_{i}"
        spheres[f"sphere_id_{i}"].cloud_id = f"sphere_id_{i}"

    return spheres


def get_mocked_com_port():
    """Mock of a serial port."""
    port = ListPortInfo("/dev/ttyUSB1234")
    port.device = "/dev/ttyUSB1234"
    port.serial_number = "1234567"
    port.manufacturer = "crownstone"
    port.description = "crownstone dongle - crownstone dongle"
    port.vid = 1234
    port.pid = 5678

    return port


def create_mocked_entry_data_conf(email: str, password: str):
    """Set a result for the entry data for comparison."""
    mock_data: dict[str, str | None] = {}
    mock_data[CONF_EMAIL] = email
    mock_data[CONF_PASSWORD] = password

    return mock_data


def create_mocked_entry_options_conf(usb_path: str | None, usb_sphere: str | None):
    """Set a result for the entry options for comparison."""
    mock_options: dict[str, str | None] = {}
    mock_options[CONF_USB_PATH] = usb_path
    mock_options[CONF_USB_SPHERE] = usb_sphere

    return mock_options


async def start_config_flow(hass: HomeAssistant, mocked_cloud: MagicMock):
    """Patch Crownstone Cloud and start the flow."""
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


async def start_options_flow(
    hass: HomeAssistant, entry_id: str, mocked_cloud: MagicMock
):
    """Patch CrownstoneEntryManager and start the flow."""
    mocked_manager = MagicMock()
    mocked_manager.cloud = mocked_cloud
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry_id] = mocked_manager

    return await hass.config_entries.options.async_init(entry_id)


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
    configured_entry_data = create_mocked_entry_data_conf(
        email="example@homeassistant.com",
        password="homeassistantisawesome",
    )
    configured_entry_options = create_mocked_entry_options_conf(
        usb_path="/dev/serial/by-id/crownstone-usb",
        usb_sphere="sphere_id",
    )

    # create mocked entry
    MockConfigEntry(
        domain=DOMAIN,
        data=configured_entry_data,
        options=configured_entry_options,
        unique_id="account_id",
    ).add_to_hass(hass)

    result = await start_config_flow(hass, get_mocked_crownstone_cloud())

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

    result = await start_config_flow(hass, cloud)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # side effect: auth error account not verified
    cloud.async_initialize.side_effect = CrownstoneAuthenticationError(
        exception_type="LOGIN_FAILED_EMAIL_NOT_VERIFIED"
    )

    result = await start_config_flow(hass, cloud)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "account_not_verified"}


async def test_unknown_error(hass: HomeAssistant):
    """Test flow with unknown error."""
    cloud = get_mocked_crownstone_cloud()
    # side effect: unknown error
    cloud.async_initialize.side_effect = CrownstoneUnknownError

    result = await start_config_flow(hass, cloud)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown_error"}


async def test_successful_login_no_usb(hass: HomeAssistant):
    """Test a successful login without configuring a USB."""
    entry_data_without_usb = create_mocked_entry_data_conf(
        email="example@homeassistant.com",
        password="homeassistantisawesome",
    )
    entry_options_without_usb = create_mocked_entry_options_conf(
        usb_path=None,
        usb_sphere=None,
    )

    result = await start_config_flow(hass, get_mocked_crownstone_cloud())
    # should show usb form
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "usb_config"

    # don't setup USB dongle, create entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: DONT_USE_USB}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == entry_data_without_usb
    assert result["options"] == entry_options_without_usb


@patch(
    "serial.tools.list_ports.comports", MagicMock(return_value=[get_mocked_com_port()])
)
@patch(
    "homeassistant.components.usb.get_serial_by_id",
    return_value="/dev/serial/by-id/crownstone-usb",
)
async def test_successful_login_with_usb(serial_mock: MagicMock, hass: HomeAssistant):
    """Test flow with correct login and usb configuration."""
    entry_data_with_usb = create_mocked_entry_data_conf(
        email="example@homeassistant.com",
        password="homeassistantisawesome",
    )
    entry_options_with_usb = create_mocked_entry_options_conf(
        usb_path="/dev/serial/by-id/crownstone-usb",
        usb_sphere="sphere_id_1",
    )

    result = await start_config_flow(
        hass, get_mocked_crownstone_cloud(create_mocked_spheres(2))
    )
    # should show usb form
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "usb_config"

    # create a mocked port
    port = get_mocked_com_port()
    port_select = usb.human_readable_device_name(
        port.device,
        port.serial_number,
        port.manufacturer,
        port.description,
        f"{hex(port.vid)[2:]:0>4}".upper(),
        f"{hex(port.pid)[2:]:0>4}".upper(),
    )

    # select a port from the list
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: port_select}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "usb_sphere_config"
    assert serial_mock.call_count == 1

    # select a sphere
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_SPHERE: "sphere_name_1"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == entry_data_with_usb
    assert result["options"] == entry_options_with_usb


@patch(
    "serial.tools.list_ports.comports", MagicMock(return_value=[get_mocked_com_port()])
)
async def test_successful_login_with_manual_usb_path(hass: HomeAssistant):
    """Test flow with correct login and usb configuration."""
    entry_data_with_manual_usb = create_mocked_entry_data_conf(
        email="example@homeassistant.com",
        password="homeassistantisawesome",
    )
    entry_options_with_manual_usb = create_mocked_entry_options_conf(
        usb_path="/dev/crownstone-usb",
        usb_sphere="sphere_id_0",
    )

    result = await start_config_flow(
        hass, get_mocked_crownstone_cloud(create_mocked_spheres(1))
    )
    # should show usb form
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "usb_config"

    # select manual from the list
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: MANUAL_PATH}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "usb_manual_config"

    # enter USB path
    path = "/dev/crownstone-usb"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_MANUAL_PATH: path}
    )

    # since we only have 1 sphere here, test that it's automatically selected and
    # creating entry without asking for user input
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == entry_data_with_manual_usb
    assert result["options"] == entry_options_with_manual_usb


@patch(
    "serial.tools.list_ports.comports", MagicMock(return_value=[get_mocked_com_port()])
)
@patch(
    "homeassistant.components.usb.get_serial_by_id",
    return_value="/dev/serial/by-id/crownstone-usb",
)
async def test_options_flow_setup_usb(serial_mock: MagicMock, hass: HomeAssistant):
    """Test options flow init."""
    configured_entry_data = create_mocked_entry_data_conf(
        email="example@homeassistant.com",
        password="homeassistantisawesome",
    )
    configured_entry_options = create_mocked_entry_options_conf(
        usb_path=None,
        usb_sphere=None,
    )

    # create mocked entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=configured_entry_data,
        options=configured_entry_options,
        unique_id="account_id",
    )
    entry.add_to_hass(hass)

    result = await start_options_flow(
        hass, entry.entry_id, get_mocked_crownstone_cloud(create_mocked_spheres(2))
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    schema = result["data_schema"].schema
    for schema_key in schema:
        if schema_key == CONF_USE_USB_OPTION:
            assert not schema_key.default()

    # USB is not set up, so this should not be in the options
    assert CONF_USB_SPHERE_OPTION not in schema

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_USE_USB_OPTION: True}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "usb_config_option"

    # create a mocked port
    port = get_mocked_com_port()
    port_select = usb.human_readable_device_name(
        port.device,
        port.serial_number,
        port.manufacturer,
        port.description,
        f"{hex(port.vid)[2:]:0>4}".upper(),
        f"{hex(port.pid)[2:]:0>4}".upper(),
    )

    # select a port from the list
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: port_select}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "usb_sphere_config_option"
    assert serial_mock.call_count == 1

    # select a sphere
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_USB_SPHERE: "sphere_name_1"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == create_mocked_entry_options_conf(
        usb_path="/dev/serial/by-id/crownstone-usb", usb_sphere="sphere_id_1"
    )


async def test_options_flow_remove_usb(hass: HomeAssistant):
    """Test selecting to set up an USB dongle."""
    configured_entry_data = create_mocked_entry_data_conf(
        email="example@homeassistant.com",
        password="homeassistantisawesome",
    )
    configured_entry_options = create_mocked_entry_options_conf(
        usb_path="/dev/serial/by-id/crownstone-usb",
        usb_sphere="sphere_id_0",
    )

    # create mocked entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=configured_entry_data,
        options=configured_entry_options,
        unique_id="account_id",
    )
    entry.add_to_hass(hass)

    result = await start_options_flow(
        hass, entry.entry_id, get_mocked_crownstone_cloud(create_mocked_spheres(2))
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    schema = result["data_schema"].schema
    for schema_key in schema:
        if schema_key == CONF_USE_USB_OPTION:
            assert schema_key.default()
        if schema_key == CONF_USB_SPHERE_OPTION:
            assert schema_key.default() == "sphere_name_0"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_USE_USB_OPTION: False,
            CONF_USB_SPHERE_OPTION: "sphere_name_0",
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == create_mocked_entry_options_conf(
        usb_path=None, usb_sphere=None
    )


@patch(
    "serial.tools.list_ports.comports", MagicMock(return_value=[get_mocked_com_port()])
)
async def test_options_flow_manual_usb_path(hass: HomeAssistant):
    """Test flow with correct login and usb configuration."""
    configured_entry_data = create_mocked_entry_data_conf(
        email="example@homeassistant.com",
        password="homeassistantisawesome",
    )
    configured_entry_options = create_mocked_entry_options_conf(
        usb_path=None,
        usb_sphere=None,
    )

    # create mocked entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=configured_entry_data,
        options=configured_entry_options,
        unique_id="account_id",
    )
    entry.add_to_hass(hass)

    result = await start_options_flow(
        hass, entry.entry_id, get_mocked_crownstone_cloud(create_mocked_spheres(1))
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_USE_USB_OPTION: True}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "usb_config_option"

    # select manual from the list
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: MANUAL_PATH}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "usb_manual_config_option"

    # enter USB path
    path = "/dev/crownstone-usb"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_USB_MANUAL_PATH: path}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == create_mocked_entry_options_conf(
        usb_path=path, usb_sphere="sphere_id_0"
    )


async def test_options_flow_change_usb_sphere(hass: HomeAssistant):
    """Test changing the usb sphere in the options."""
    configured_entry_data = create_mocked_entry_data_conf(
        email="example@homeassistant.com",
        password="homeassistantisawesome",
    )
    configured_entry_options = create_mocked_entry_options_conf(
        usb_path="/dev/serial/by-id/crownstone-usb",
        usb_sphere="sphere_id_0",
    )

    # create mocked entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=configured_entry_data,
        options=configured_entry_options,
        unique_id="account_id",
    )
    entry.add_to_hass(hass)

    result = await start_options_flow(
        hass, entry.entry_id, get_mocked_crownstone_cloud(create_mocked_spheres(3))
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_USE_USB_OPTION: True, CONF_USB_SPHERE_OPTION: "sphere_name_2"},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == create_mocked_entry_options_conf(
        usb_path="/dev/serial/by-id/crownstone-usb", usb_sphere="sphere_id_2"
    )
