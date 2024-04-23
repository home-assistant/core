"""Tests for the Crownstone integration."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from crownstone_cloud.cloud_models.spheres import Spheres
from crownstone_cloud.exceptions import (
    CrownstoneAuthenticationError,
    CrownstoneUnknownError,
)
import pytest
from serial.tools.list_ports_common import ListPortInfo

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
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MockFixture = Generator[MagicMock | AsyncMock, None, None]


@pytest.fixture(name="crownstone_setup")
def crownstone_setup() -> MockFixture:
    """Mock Crownstone entry setup."""
    with patch(
        "homeassistant.components.crownstone.async_setup_entry", return_value=True
    ) as setup_mock:
        yield setup_mock


@pytest.fixture(name="pyserial_comports")
def usb_comports() -> MockFixture:
    """Mock pyserial comports."""
    with patch(
        "serial.tools.list_ports.comports",
        MagicMock(return_value=[get_mocked_com_port()]),
    ) as comports_mock:
        yield comports_mock


@pytest.fixture(name="pyserial_comports_none_types")
def usb_comports_none_types() -> MockFixture:
    """Mock pyserial comports."""
    with patch(
        "serial.tools.list_ports.comports",
        MagicMock(return_value=[get_mocked_com_port_none_types()]),
    ) as comports_mock:
        yield comports_mock


@pytest.fixture(name="usb_path")
def usb_path() -> MockFixture:
    """Mock usb serial path."""
    with patch(
        "homeassistant.components.usb.get_serial_by_id",
        return_value="/dev/serial/by-id/crownstone-usb",
    ) as usb_path_mock:
        yield usb_path_mock


def get_mocked_crownstone_entry_manager(mocked_cloud: MagicMock):
    """Get a mocked CrownstoneEntryManager instance."""
    mocked_entry_manager = MagicMock()
    mocked_entry_manager.async_setup = AsyncMock(return_value=True)
    mocked_entry_manager.cloud = mocked_cloud

    return mocked_entry_manager


def get_mocked_crownstone_cloud(spheres: dict[str, MagicMock] | None = None):
    """Return a mocked Crownstone Cloud instance."""
    mock_cloud = MagicMock()
    mock_cloud.async_initialize = AsyncMock()
    mock_cloud.cloud_data = Spheres(MagicMock(), "account_id")
    mock_cloud.cloud_data.data = spheres

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


def get_mocked_com_port_none_types():
    """Mock of a serial port with NoneTypes."""
    port = ListPortInfo("/dev/ttyUSB1234")
    port.device = "/dev/ttyUSB1234"
    port.serial_number = None
    port.manufacturer = None
    port.description = "crownstone dongle - crownstone dongle"
    port.vid = None
    port.pid = None

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
        return await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=mocked_login_input
        )


async def start_options_flow(
    hass: HomeAssistant, entry_id: str, mocked_manager: MagicMock
):
    """Patch CrownstoneEntryManager and start the flow."""
    # set up integration
    with patch(
        "homeassistant.components.crownstone.CrownstoneEntryManager",
        return_value=mocked_manager,
    ):
        await hass.config_entries.async_setup(entry_id)

    return await hass.config_entries.options.async_init(entry_id)


async def test_no_user_input(
    crownstone_setup: MockFixture, hass: HomeAssistant
) -> None:
    """Test the flow done in the correct way."""
    # test if a form is returned if no input is provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    # show the login form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert crownstone_setup.call_count == 0


async def test_abort_if_configured(
    crownstone_setup: MockFixture, hass: HomeAssistant
) -> None:
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
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert crownstone_setup.call_count == 0


async def test_authentication_errors(
    crownstone_setup: MockFixture, hass: HomeAssistant
) -> None:
    """Test flow with wrong auth errors."""
    cloud = get_mocked_crownstone_cloud()
    # side effect: auth error login failed
    cloud.async_initialize.side_effect = CrownstoneAuthenticationError(
        exception_type="LOGIN_FAILED"
    )

    result = await start_config_flow(hass, cloud)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # side effect: auth error account not verified
    cloud.async_initialize.side_effect = CrownstoneAuthenticationError(
        exception_type="LOGIN_FAILED_EMAIL_NOT_VERIFIED"
    )

    result = await start_config_flow(hass, cloud)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "account_not_verified"}
    assert crownstone_setup.call_count == 0


async def test_unknown_error(
    crownstone_setup: MockFixture, hass: HomeAssistant
) -> None:
    """Test flow with unknown error."""
    cloud = get_mocked_crownstone_cloud()
    # side effect: unknown error
    cloud.async_initialize.side_effect = CrownstoneUnknownError

    result = await start_config_flow(hass, cloud)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown_error"}
    assert crownstone_setup.call_count == 0


async def test_successful_login_no_usb(
    crownstone_setup: MockFixture, hass: HomeAssistant
) -> None:
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_config"

    # don't setup USB dongle, create entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: DONT_USE_USB}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data_without_usb
    assert result["options"] == entry_options_without_usb
    assert crownstone_setup.call_count == 1


async def test_successful_login_with_usb(
    crownstone_setup: MockFixture,
    pyserial_comports_none_types: MockFixture,
    usb_path: MockFixture,
    hass: HomeAssistant,
) -> None:
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_config"
    assert pyserial_comports_none_types.call_count == 1

    # create a mocked port which should be in
    # the list returned from list_ports_as_str, from .helpers
    port = get_mocked_com_port_none_types()
    port_select = usb.human_readable_device_name(
        port.device,
        port.serial_number,
        port.manufacturer,
        port.description,
        port.vid,
        port.pid,
    )

    # select a port from the list
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: port_select}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_sphere_config"
    assert pyserial_comports_none_types.call_count == 2
    assert usb_path.call_count == 1

    # select a sphere
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_SPHERE: "sphere_name_1"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data_with_usb
    assert result["options"] == entry_options_with_usb
    assert crownstone_setup.call_count == 1


async def test_successful_login_with_manual_usb_path(
    crownstone_setup: MockFixture, pyserial_comports: MockFixture, hass: HomeAssistant
) -> None:
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_config"
    assert pyserial_comports.call_count == 1

    # select manual from the list
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: MANUAL_PATH}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_manual_config"
    assert pyserial_comports.call_count == 2

    # enter USB path
    path = "/dev/crownstone-usb"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_MANUAL_PATH: path}
    )

    # since we only have 1 sphere here, test that it's automatically selected and
    # creating entry without asking for user input
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data_with_manual_usb
    assert result["options"] == entry_options_with_manual_usb
    assert crownstone_setup.call_count == 1


async def test_options_flow_setup_usb(
    pyserial_comports: MockFixture, usb_path: MockFixture, hass: HomeAssistant
) -> None:
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
        hass,
        entry.entry_id,
        get_mocked_crownstone_entry_manager(
            get_mocked_crownstone_cloud(create_mocked_spheres(2))
        ),
    )

    assert result["type"] is FlowResultType.FORM
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_config"
    assert pyserial_comports.call_count == 1

    # create a mocked port which should be in
    # the list returned from list_ports_as_str, from .helpers
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_sphere_config"
    assert pyserial_comports.call_count == 2
    assert usb_path.call_count == 1

    # select a sphere
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_USB_SPHERE: "sphere_name_1"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == create_mocked_entry_options_conf(
        usb_path="/dev/serial/by-id/crownstone-usb", usb_sphere="sphere_id_1"
    )


async def test_options_flow_remove_usb(hass: HomeAssistant) -> None:
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
        hass,
        entry.entry_id,
        get_mocked_crownstone_entry_manager(
            get_mocked_crownstone_cloud(create_mocked_spheres(2))
        ),
    )

    assert result["type"] is FlowResultType.FORM
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
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == create_mocked_entry_options_conf(
        usb_path=None, usb_sphere=None
    )


async def test_options_flow_manual_usb_path(
    pyserial_comports: MockFixture, hass: HomeAssistant
) -> None:
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
        hass,
        entry.entry_id,
        get_mocked_crownstone_entry_manager(
            get_mocked_crownstone_cloud(create_mocked_spheres(1))
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_USE_USB_OPTION: True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_config"
    assert pyserial_comports.call_count == 1

    # select manual from the list
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: MANUAL_PATH}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_manual_config"
    assert pyserial_comports.call_count == 2

    # enter USB path
    path = "/dev/crownstone-usb"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_USB_MANUAL_PATH: path}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == create_mocked_entry_options_conf(
        usb_path=path, usb_sphere="sphere_id_0"
    )


async def test_options_flow_change_usb_sphere(hass: HomeAssistant) -> None:
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
        hass,
        entry.entry_id,
        get_mocked_crownstone_entry_manager(
            get_mocked_crownstone_cloud(create_mocked_spheres(3))
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_USE_USB_OPTION: True, CONF_USB_SPHERE_OPTION: "sphere_name_2"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == create_mocked_entry_options_conf(
        usb_path="/dev/serial/by-id/crownstone-usb", usb_sphere="sphere_id_2"
    )
