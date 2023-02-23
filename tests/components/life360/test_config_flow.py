"""Test the Life360 config flow."""
from unittest.mock import patch

from life360 import Life360Error, LoginError
import pytest
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.life360.const import (
    CONF_AUTHORIZATION,
    CONF_DRIVING_SPEED,
    CONF_MAX_GPS_ACCURACY,
    DEFAULT_OPTIONS,
    DOMAIN,
    SHOW_DRIVING,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_USER = "Test@Test.com"
TEST_PW = "password"
TEST_PW_3 = "password_3"
TEST_AUTHORIZATION = "authorization_string"
TEST_AUTHORIZATION_2 = "authorization_string_2"
TEST_AUTHORIZATION_3 = "authorization_string_3"
TEST_MAX_GPS_ACCURACY = "300"
TEST_DRIVING_SPEED = "18"
TEST_SHOW_DRIVING = True

USER_INPUT = {CONF_USERNAME: TEST_USER, CONF_PASSWORD: TEST_PW}

TEST_CONFIG_DATA = {
    CONF_USERNAME: TEST_USER,
    CONF_PASSWORD: TEST_PW,
    CONF_AUTHORIZATION: TEST_AUTHORIZATION,
}
TEST_CONFIG_DATA_2 = {
    CONF_USERNAME: TEST_USER,
    CONF_PASSWORD: TEST_PW,
    CONF_AUTHORIZATION: TEST_AUTHORIZATION_2,
}
TEST_CONFIG_DATA_3 = {
    CONF_USERNAME: TEST_USER,
    CONF_PASSWORD: TEST_PW_3,
    CONF_AUTHORIZATION: TEST_AUTHORIZATION_3,
}

USER_OPTIONS = {
    "limit_gps_acc": True,
    CONF_MAX_GPS_ACCURACY: TEST_MAX_GPS_ACCURACY,
    "set_drive_speed": True,
    CONF_DRIVING_SPEED: TEST_DRIVING_SPEED,
    SHOW_DRIVING: TEST_SHOW_DRIVING,
}
TEST_OPTIONS = {
    CONF_MAX_GPS_ACCURACY: float(TEST_MAX_GPS_ACCURACY),
    CONF_DRIVING_SPEED: float(TEST_DRIVING_SPEED),
    SHOW_DRIVING: TEST_SHOW_DRIVING,
}


# ========== Common Fixtures & Functions ===============================================


@pytest.fixture(name="life360", autouse=True)
def life360_fixture():
    """Mock life360 config entry setup & unload."""
    with patch(
        "homeassistant.components.life360.async_setup_entry", return_value=True
    ), patch("homeassistant.components.life360.async_unload_entry", return_value=True):
        yield


@pytest.fixture
def life360_api():
    """Mock Life360 api."""
    with patch(
        "homeassistant.components.life360.config_flow.Life360", autospec=True
    ) as mock:
        yield mock.return_value


def create_config_entry(hass, state=None):
    """Create mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_DATA,
        version=1,
        state=state,
        options=DEFAULT_OPTIONS,
        unique_id=TEST_USER.lower(),
    )
    config_entry.add_to_hass(hass)
    return config_entry


# ========== User Flow Tests ===========================================================


async def test_user_show_form(hass: HomeAssistant, life360_api) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    life360_api.get_authorization.assert_not_called()

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    schema = result["data_schema"].schema
    assert set(schema) == set(USER_INPUT)
    # username and password fields should be empty.
    keys = list(schema)
    for key in USER_INPUT:
        assert keys[keys.index(key)].default == vol.UNDEFINED


async def test_user_config_flow_success(hass: HomeAssistant, life360_api) -> None:
    """Test a successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    life360_api.get_authorization.return_value = TEST_AUTHORIZATION

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    life360_api.get_authorization.assert_called_once()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USER.lower()
    assert result["data"] == TEST_CONFIG_DATA
    assert result["options"] == DEFAULT_OPTIONS


@pytest.mark.parametrize(
    ("exception", "error"),
    [(LoginError, "invalid_auth"), (Life360Error, "cannot_connect")],
)
async def test_user_config_flow_error(
    hass: HomeAssistant, life360_api, caplog: pytest.LogCaptureFixture, exception, error
) -> None:
    """Test a user config flow with an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    life360_api.get_authorization.side_effect = exception("test reason")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    life360_api.get_authorization.assert_called_once()

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]
    assert result["errors"]["base"] == error

    assert "test reason" in caplog.text

    schema = result["data_schema"].schema
    assert set(schema) == set(USER_INPUT)
    # username and password fields should be prefilled with current values.
    keys = list(schema)
    for key, val in USER_INPUT.items():
        default = keys[keys.index(key)].default
        assert default != vol.UNDEFINED
        assert default() == val


async def test_user_config_flow_already_configured(
    hass: HomeAssistant, life360_api
) -> None:
    """Test a user config flow with an account already configured."""
    create_config_entry(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    life360_api.get_authorization.assert_not_called()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ========== Reauth Flow Tests =========================================================


@pytest.mark.parametrize("state", [None, config_entries.ConfigEntryState.LOADED])
async def test_reauth_config_flow_success(
    hass: HomeAssistant, life360_api, caplog: pytest.LogCaptureFixture, state
) -> None:
    """Test a successful reauthorization config flow."""
    config_entry = create_config_entry(hass, state=state)

    # Simulate current username & password are still valid, but authorization string has
    # expired, such that getting a new authorization string from server is successful.
    life360_api.get_authorization.return_value = TEST_AUTHORIZATION_2

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
            "title_placeholders": {"name": config_entry.title},
            "unique_id": config_entry.unique_id,
        },
        data=config_entry.data,
    )
    await hass.async_block_till_done()

    life360_api.get_authorization.assert_called_once()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert "Reauthorization successful" in caplog.text

    assert config_entry.data == TEST_CONFIG_DATA_2


async def test_reauth_config_flow_login_error(
    hass: HomeAssistant, life360_api, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a reauthorization config flow with a login error."""
    config_entry = create_config_entry(hass)

    # Simulate current username & password are invalid, which results in a form
    # requesting new password, with old password as default value.
    life360_api.get_authorization.side_effect = LoginError("test reason")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
            "title_placeholders": {"name": config_entry.title},
            "unique_id": config_entry.unique_id,
        },
        data=config_entry.data,
    )
    await hass.async_block_till_done()

    life360_api.get_authorization.assert_called_once()

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]
    assert result["errors"]["base"] == "invalid_auth"

    assert "test reason" in caplog.text

    schema = result["data_schema"].schema
    assert len(schema) == 1
    assert "password" in schema
    key = list(schema)[0]
    assert key.default() == TEST_PW

    # Simulate getting a new, valid password.
    life360_api.get_authorization.reset_mock(side_effect=True)
    life360_api.get_authorization.return_value = TEST_AUTHORIZATION_3

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: TEST_PW_3}
    )
    await hass.async_block_till_done()

    life360_api.get_authorization.assert_called_once()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert "Reauthorization successful" in caplog.text

    assert config_entry.data == TEST_CONFIG_DATA_3


# ========== Option flow Tests =========================================================


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test an options flow."""
    config_entry = create_config_entry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    assert not result["errors"]

    schema = result["data_schema"].schema
    assert set(schema) == set(USER_OPTIONS)

    flow_id = result["flow_id"]

    result = await hass.config_entries.options.async_configure(flow_id, USER_OPTIONS)

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == TEST_OPTIONS

    assert config_entry.options == TEST_OPTIONS
