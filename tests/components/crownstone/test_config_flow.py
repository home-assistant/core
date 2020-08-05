"""Tests for the Crownstone integration."""
from crownstone_cloud.exceptions import (
    CrownstoneAuthenticationError,
    CrownstoneUnknownError,
)
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.crownstone.const import CONF_SPHERE, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_ID, CONF_PASSWORD

from tests.async_mock import AsyncMock, Mock, patch
from tests.common import MockConfigEntry

MOCK_CONF = dict()


@pytest.fixture(name="crownstone_setup", autouse=True)
def crownstone_setup():
    """Mock Crownstone entry setup."""
    with patch(
        "homeassistant.components.crownstone.async_setup_entry", return_value=True
    ):
        yield


def get_mocked_crownstone_cloud(spheres: dict):
    """Return a mocked Crownstone Cloud instance."""
    mock_cloud = Mock()
    mock_cloud.reset = Mock()
    mock_cloud.spheres = Mock()
    mock_cloud.spheres.async_update_sphere_data = AsyncMock()
    mock_cloud.spheres.spheres = spheres
    mock_cloud.spheres.__iter__ = Mock(
        return_value=iter(mock_cloud.spheres.spheres.values())
    )
    mock_cloud.async_login = AsyncMock()

    return mock_cloud


def get_mocked_sphere_data(entries: int):
    """Return a mocked sphere dict for Crownstone Cloud."""
    sphere_dict = {}
    for entry in range(1, (entries + 1), 1):
        sphere_dict[f"sphere_id_{str(entry)}"] = Mock()
        sphere_dict[f"sphere_id_{str(entry)}"].name = f"sphere_name_{str(entry)}"

    return sphere_dict


def create_mocked_entry_conf(
    unique_id: str, email: str, password: str, sphere_name: str
):
    """Set a result for the entry for comparison."""
    MOCK_CONF[CONF_ID] = unique_id
    MOCK_CONF[CONF_EMAIL] = email
    MOCK_CONF[CONF_PASSWORD] = password
    MOCK_CONF[CONF_SPHERE] = sphere_name


async def start_flow(hass, mocked_cloud: Mock):
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


async def test_no_user_input(hass):
    """Test the flow done in the correct way."""
    # test if a form is returned if no input is provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    # show the login form
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_successful_login_1_sphere_configured(hass):
    """Test flow with correct login input and 1 sphere configured."""
    # create a Crownstone Cloud mock
    # test with 1 sphere
    cloud = get_mocked_crownstone_cloud(get_mocked_sphere_data(1))

    # create mock entry conf
    create_mocked_entry_conf(
        unique_id="sphere_name_1",
        email="example@homeassistant.com",
        password="homeassistantisawesome",
        sphere_name="sphere_name_1",
    )

    result = await start_flow(hass, cloud)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == MOCK_CONF
    cloud.reset.assert_called()


async def test_successful_login_multiple_spheres_configured(hass):
    """Test flow with correct login input and multiple spheres configured."""
    # create a Crownstone Cloud mock
    # test with 2 spheres (most common, if multiple are set up at all)
    cloud = get_mocked_crownstone_cloud(get_mocked_sphere_data(2))

    # create mock entry conf
    create_mocked_entry_conf(
        unique_id="sphere_name_1",
        email="example@homeassistant.com",
        password="homeassistantisawesome",
        sphere_name="sphere_name_1",
    )

    result = await start_flow(hass, cloud)

    # show the sphere form
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "sphere"


async def test_abort_if_configured(hass):
    """Test flow with correct login input and abort if sphere already configured."""
    # create mock entry conf
    create_mocked_entry_conf(
        unique_id="sphere_name_1",
        email="example@homeassistant.com",
        password="homeassistantisawesome",
        sphere_name="sphere_name_1",
    )

    # create mocked entry
    MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONF, unique_id=MOCK_CONF[CONF_ID],
    ).add_to_hass(hass)

    cloud = get_mocked_crownstone_cloud(get_mocked_sphere_data(1))

    result = await start_flow(hass, cloud)

    # test if we abort if we try to configure the same entry
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_authentication_errors(hass):
    """Test flow with wrong auth errors."""
    cloud = get_mocked_crownstone_cloud(get_mocked_sphere_data(1))
    # side effect: auth error login failed
    cloud.async_login.side_effect = CrownstoneAuthenticationError(type="LOGIN_FAILED")

    result = await start_flow(hass, cloud)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # side effect: auth error account not verified
    cloud.async_login.side_effect = CrownstoneAuthenticationError(
        type="LOGIN_FAILED_EMAIL_NOT_VERIFIED"
    )

    result = await start_flow(hass, cloud)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "account_not_verified"}

    # side effect: auth error no email/password provided
    cloud.async_login.side_effect = CrownstoneAuthenticationError(
        type="USERNAME_EMAIL_REQUIRED"
    )

    result = await start_flow(hass, cloud)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "auth_input_none"}


async def test_unknown_error(hass):
    """Test flow with unknown error."""
    cloud = get_mocked_crownstone_cloud(get_mocked_sphere_data(1))
    # side effect: unknown error
    cloud.async_login.side_effect = CrownstoneUnknownError

    result = await start_flow(hass, cloud)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown_error"}
