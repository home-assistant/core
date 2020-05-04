"""Tests for the Toon config flow."""

import pytest
from toonapilib.toonapilibexceptions import (
    AgreementsRetrievalError,
    InvalidConsumerKey,
    InvalidConsumerSecret,
    InvalidCredentials,
)

from homeassistant import data_entry_flow
from homeassistant.components.toon import config_flow
from homeassistant.components.toon.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DISPLAY,
    CONF_TENANT,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry

FIXTURE_APP = {
    DOMAIN: {CONF_CLIENT_ID: "1234567890abcdef", CONF_CLIENT_SECRET: "1234567890abcdef"}
}

FIXTURE_CREDENTIALS = {
    CONF_USERNAME: "john.doe",
    CONF_PASSWORD: "secret",
    CONF_TENANT: "eneco",
}

FIXTURE_DISPLAY = {CONF_DISPLAY: "display1"}


@pytest.fixture
def mock_toonapilib():
    """Mock toonapilib."""
    with patch("homeassistant.components.toon.config_flow.Toon") as Toon:
        Toon().display_names = [FIXTURE_DISPLAY[CONF_DISPLAY]]
        yield Toon


async def setup_component(hass):
    """Set up Toon component."""
    with patch("os.path.isfile", return_value=False):
        assert await async_setup_component(hass, DOMAIN, FIXTURE_APP)
        await hass.async_block_till_done()


async def test_abort_if_no_app_configured(hass):
    """Test abort if no app is configured."""
    flow = config_flow.ToonFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_app"


async def test_show_authenticate_form(hass):
    """Test that the authentication form is served."""
    await setup_component(hass)

    flow = config_flow.ToonFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "authenticate"


@pytest.mark.parametrize(
    "side_effect,reason",
    [
        (InvalidConsumerKey, "client_id"),
        (InvalidConsumerSecret, "client_secret"),
        (AgreementsRetrievalError, "no_agreements"),
        (Exception, "unknown_auth_fail"),
    ],
)
async def test_toon_abort(hass, mock_toonapilib, side_effect, reason):
    """Test we abort on Toon error."""
    await setup_component(hass)

    flow = config_flow.ToonFlowHandler()
    flow.hass = hass

    mock_toonapilib.side_effect = side_effect

    result = await flow.async_step_authenticate(user_input=FIXTURE_CREDENTIALS)

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == reason


async def test_invalid_credentials(hass, mock_toonapilib):
    """Test we show authentication form on Toon auth error."""
    mock_toonapilib.side_effect = InvalidCredentials

    await setup_component(hass)

    flow = config_flow.ToonFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=FIXTURE_CREDENTIALS)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "authenticate"
    assert result["errors"] == {"base": "credentials"}


async def test_full_flow_implementation(hass, mock_toonapilib):
    """Test registering an integration and finishing flow works."""
    await setup_component(hass)

    flow = config_flow.ToonFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "authenticate"

    result = await flow.async_step_user(user_input=FIXTURE_CREDENTIALS)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "display"

    result = await flow.async_step_display(user_input=FIXTURE_DISPLAY)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == FIXTURE_DISPLAY[CONF_DISPLAY]
    assert result["data"][CONF_USERNAME] == FIXTURE_CREDENTIALS[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_CREDENTIALS[CONF_PASSWORD]
    assert result["data"][CONF_TENANT] == FIXTURE_CREDENTIALS[CONF_TENANT]
    assert result["data"][CONF_DISPLAY] == FIXTURE_DISPLAY[CONF_DISPLAY]


async def test_no_displays(hass, mock_toonapilib):
    """Test abort when there are no displays."""
    await setup_component(hass)

    mock_toonapilib().display_names = []

    flow = config_flow.ToonFlowHandler()
    flow.hass = hass
    await flow.async_step_user(user_input=FIXTURE_CREDENTIALS)

    result = await flow.async_step_display(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_displays"


async def test_display_already_exists(hass, mock_toonapilib):
    """Test showing display form again if display already exists."""
    await setup_component(hass)

    flow = config_flow.ToonFlowHandler()
    flow.hass = hass
    await flow.async_step_user(user_input=FIXTURE_CREDENTIALS)

    MockConfigEntry(domain=DOMAIN, data=FIXTURE_DISPLAY).add_to_hass(hass)

    result = await flow.async_step_display(user_input=FIXTURE_DISPLAY)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "display"
    assert result["errors"] == {"base": "display_exists"}


async def test_abort_last_minute_fail(hass, mock_toonapilib):
    """Test we abort when API communication fails in the last step."""
    await setup_component(hass)

    flow = config_flow.ToonFlowHandler()
    flow.hass = hass
    await flow.async_step_user(user_input=FIXTURE_CREDENTIALS)

    mock_toonapilib.side_effect = Exception

    result = await flow.async_step_display(user_input=FIXTURE_DISPLAY)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "unknown_auth_fail"
