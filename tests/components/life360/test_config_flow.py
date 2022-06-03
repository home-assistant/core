"""Test the Life360 config flow."""

from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.life360.const import (
    CONF_AUTHORIZATION,
    CONF_DRIVING_SPEED,
    CONF_MAX_GPS_ACCURACY,
    CONF_PREFIX,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_SEC,
    DOMAIN,
    SHOW_DRIVING,
)
from homeassistant.components.life360.helpers import init_integ_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

TEST_USER = "Test@Test.com"
TEST_PW = "password"
TEST_PW_2 = "password_2"
TEST_PW_3 = "password_3"
TEST_AUTHORIZATION = "authorization_string"
TEST_AUTHORIZATION_2 = "authorization_string_2"
TEST_AUTHORIZATION_3 = "authorization_string_3"
TEST_PREFIX = "life360"
TEST_MAX_GPS_ACCURACY = "300"
TEST_DRIVING_SPEED = "18"
TEST_SCAN_INTERVAL = "10"
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
TEST_DEF_OPTIONS = {CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SEC}

USER_OPTIONS = {
    "use_prefix": True,
    CONF_PREFIX: TEST_PREFIX,
    "limit_gps_acc": True,
    CONF_MAX_GPS_ACCURACY: TEST_MAX_GPS_ACCURACY,
    "set_drive_speed": True,
    CONF_DRIVING_SPEED: TEST_DRIVING_SPEED,
    CONF_SCAN_INTERVAL: TEST_SCAN_INTERVAL,
    SHOW_DRIVING: TEST_SHOW_DRIVING,
}
TEST_OPTIONS = {
    CONF_PREFIX: TEST_PREFIX,
    CONF_MAX_GPS_ACCURACY: float(TEST_MAX_GPS_ACCURACY),
    CONF_DRIVING_SPEED: float(TEST_DRIVING_SPEED),
    CONF_SCAN_INTERVAL: float(TEST_SCAN_INTERVAL),
    SHOW_DRIVING: TEST_SHOW_DRIVING,
}

USER_INPUT_AND_OPTIONS = USER_INPUT | USER_OPTIONS


@pytest.fixture(name="life360", autouse=True)
def life360_fixture():
    """Mock life360."""
    with patch("homeassistant.components.life360.config_flow.get_life360_api"), patch(
        "homeassistant.components.life360.async_setup_entry", return_value=True
    ):
        yield


async def _start_flow(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    return result


def _authorization_login_error(hass, api, username, password, errors):
    errors["base"] = "invalid_auth"
    return None


def _test_config_entry(hass, options=None):
    options = options or TEST_DEF_OPTIONS
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_DATA,
        version=2,
        options=options,
        unique_id=TEST_USER.lower(),
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await _start_flow(hass)

    schema = result["data_schema"].schema
    assert set(schema.keys()) == set(USER_INPUT_AND_OPTIONS.keys())
    # username and password fields should be empty.
    keys = list(schema.keys())
    for key in USER_INPUT:
        assert keys[keys.index(key)].default == vol.UNDEFINED


async def test_config_flow_success_defaults(hass):
    """Test a successful config flow with default options."""
    result = await _start_flow(hass)
    flow_id = result["flow_id"]

    with patch(
        "homeassistant.components.life360.config_flow.get_life360_authorization",
        return_value=TEST_AUTHORIZATION,
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == TEST_USER.lower()
    assert result["data"] == TEST_CONFIG_DATA
    assert result["options"] == TEST_DEF_OPTIONS

    assert DOMAIN in hass.data
    assert TEST_USER.lower() in hass.data[DOMAIN]["accounts"]


async def test_config_flow_success_all_options(hass):
    """Test a successful config flow with all options entered by user."""
    result = await _start_flow(hass)
    flow_id = result["flow_id"]

    with patch(
        "homeassistant.components.life360.config_flow.get_life360_authorization",
        return_value=TEST_AUTHORIZATION,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, USER_INPUT_AND_OPTIONS
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == TEST_USER.lower()
    assert result["data"] == TEST_CONFIG_DATA
    assert result["options"] == TEST_OPTIONS


async def test_config_flow_login_error(hass):
    """Test a config flow with a login error."""
    result = await _start_flow(hass)
    flow_id = result["flow_id"]

    with patch(
        "homeassistant.components.life360.config_flow.get_life360_authorization",
        side_effect=_authorization_login_error,
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"]

    schema = result["data_schema"].schema
    assert set(schema.keys()) == set(USER_INPUT_AND_OPTIONS.keys())
    # username and password fields should be prefilled with current values.
    keys = list(schema.keys())
    for key, val in USER_INPUT.items():
        default = keys[keys.index(key)].default
        assert default != vol.UNDEFINED
        assert default() == val


async def test_config_flow_already_configured(hass):
    """Test a config flow with an account already configured."""
    _test_config_entry(hass)

    result = await _start_flow(hass)
    flow_id = result["flow_id"]

    with patch(
        "homeassistant.components.life360.config_flow.get_life360_authorization",
        return_value=TEST_AUTHORIZATION,
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


def _start_reauth_flow(hass):
    config_entry = _test_config_entry(hass)

    init_integ_data(hass)
    hass.data[DOMAIN]["accounts"][config_entry.unique_id] = {"api": MagicMock()}

    return config_entry


async def test_config_flow_reauth_success(hass):
    """Test a successful reauthorization config flow."""
    config_entry = _start_reauth_flow(hass)

    # Simulate current username & password are still valid, but authorization string has
    # expired, such that getting a new authorization string from server is successful.
    with patch(
        "homeassistant.components.life360.config_flow.get_life360_authorization",
        return_value=TEST_AUTHORIZATION_2,
    ):
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

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"

    assert config_entry.data == TEST_CONFIG_DATA_2


async def test_config_flow_reauth_login_error(hass):
    """Test a reauthorization config flow with a login error."""
    config_entry = _start_reauth_flow(hass)

    # Simulate current username & password are invalid, which results in a form
    # requesting new password (with current password hidden.)
    with patch(
        "homeassistant.components.life360.config_flow.get_life360_authorization",
        side_effect=_authorization_login_error,
    ):
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

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]

    # First form opened should NOT show current password; i.e., password entry in schema
    # should have vol.UNDEFINED as default value.
    schema = result["data_schema"].schema
    assert len(schema) == 1
    assert "password" in schema
    key = list(schema.keys())[0]
    assert key.default == vol.UNDEFINED

    flow_id = result["flow_id"]

    # Simulate getting a password that still isn't valid, which results in a form
    # requesting new password (but this time showing current password.)
    with patch(
        "homeassistant.components.life360.config_flow.get_life360_authorization",
        side_effect=_authorization_login_error,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_PASSWORD: TEST_PW_2}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]

    # This form opened SHOULD show current password; i.e., password entry in schema
    # should have a default value other than vol.UNDEFINED. In fact, it should be a
    # function that returns the current password.
    schema = result["data_schema"].schema
    assert len(schema) == 1
    assert "password" in schema
    key = list(schema.keys())[0]
    assert key.default != vol.UNDEFINED
    assert key.default() == TEST_PW_2

    # Simulate getting a new, valid password.
    with patch(
        "homeassistant.components.life360.config_flow.get_life360_authorization",
        return_value=TEST_AUTHORIZATION_3,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_PASSWORD: TEST_PW_3}
        )

    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"

    assert config_entry.data == TEST_CONFIG_DATA_3


async def test_options_flow_all(hass):
    """Test an options flow changing all options."""
    config_entry = _test_config_entry(hass)

    init_integ_data(hass)
    hass.data[DOMAIN]["accounts"][config_entry.unique_id] = {}

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert not result["errors"]

    schema = result["data_schema"].schema
    assert set(schema.keys()) == set(USER_OPTIONS.keys())

    flow_id = result["flow_id"]

    result = await hass.config_entries.options.async_configure(flow_id, USER_OPTIONS)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == TEST_OPTIONS

    assert hass.data[DOMAIN]["accounts"][config_entry.unique_id]["re_add_entry"]
    assert config_entry.options == TEST_OPTIONS


async def test_options_flow_fixed_prefix(hass):
    """Test an options flow where prefix does not change."""
    config_entry = _test_config_entry(hass, TEST_OPTIONS)

    init_integ_data(hass)
    hass.data[DOMAIN]["accounts"][config_entry.unique_id] = {}

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert not result["errors"]

    schema = result["data_schema"].schema
    assert set(schema.keys()) == set(USER_OPTIONS.keys())

    flow_id = result["flow_id"]

    user_options = USER_OPTIONS | {SHOW_DRIVING: not TEST_SHOW_DRIVING}
    test_options = TEST_OPTIONS | {SHOW_DRIVING: not TEST_SHOW_DRIVING}

    result = await hass.config_entries.options.async_configure(flow_id, user_options)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == test_options

    assert not hass.data[DOMAIN]["accounts"][config_entry.unique_id]["re_add_entry"]
    assert config_entry.options == test_options
