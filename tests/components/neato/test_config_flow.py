"""Tests for the Neato config flow."""
from pybotvac.exceptions import NeatoLoginException, NeatoRobotException
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.neato import config_flow
from homeassistant.components.neato.const import CONF_VENDOR, NEATO_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.async_mock import patch
from tests.common import MockConfigEntry

USERNAME = "myUsername"
PASSWORD = "myPassword"
VENDOR_NEATO = "neato"
VENDOR_VORWERK = "vorwerk"
VENDOR_INVALID = "invalid"


@pytest.fixture(name="account")
def mock_controller_login():
    """Mock a successful login."""
    with patch("homeassistant.components.neato.config_flow.Account", return_value=True):
        yield


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.NeatoConfigFlow()
    flow.hass = hass
    return flow


async def test_user(hass, account):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await flow.async_step_user(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_VENDOR: VENDOR_NEATO}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_VENDOR] == VENDOR_NEATO

    result = await flow.async_step_user(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_VENDOR: VENDOR_VORWERK}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_VENDOR] == VENDOR_VORWERK


async def test_import(hass, account):
    """Test import step."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_VENDOR: VENDOR_NEATO}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"{USERNAME} (from configuration)"
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_VENDOR] == VENDOR_NEATO


async def test_abort_if_already_setup(hass, account):
    """Test we abort if Neato is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain=NEATO_DOMAIN,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_VENDOR: VENDOR_NEATO,
        },
    ).add_to_hass(hass)

    # Should fail, same USERNAME (import)
    result = await flow.async_step_import(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_VENDOR: VENDOR_NEATO}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Should fail, same USERNAME (flow)
    result = await flow.async_step_user(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_VENDOR: VENDOR_NEATO}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_abort_on_invalid_credentials(hass):
    """Test when we have invalid credentials."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.neato.config_flow.Account",
        side_effect=NeatoLoginException(),
    ):
        result = await flow.async_step_user(
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_VENDOR: VENDOR_NEATO,
            }
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "invalid_credentials"}

        result = await flow.async_step_import(
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_VENDOR: VENDOR_NEATO,
            }
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "invalid_credentials"


async def test_abort_on_unexpected_error(hass):
    """Test when we have an unexpected error."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.neato.config_flow.Account",
        side_effect=NeatoRobotException(),
    ):
        result = await flow.async_step_user(
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_VENDOR: VENDOR_NEATO,
            }
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unexpected_error"}

        result = await flow.async_step_import(
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_VENDOR: VENDOR_NEATO,
            }
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "unexpected_error"
