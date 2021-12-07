"""Tests for the Abode config flow."""
from unittest.mock import patch

from elmax_api.exceptions import ElmaxBadLoginError, ElmaxBadPinError, ElmaxNetworkError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.elmax.const import (
    CONF_ELMAX_PANEL_ID,
    CONF_ELMAX_PANEL_NAME,
    CONF_ELMAX_PANEL_PIN,
    CONF_ELMAX_PASSWORD,
    CONF_ELMAX_USERNAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.data_entry_flow import FlowResult

from tests.components.elmax import (
    MOCK_PANEL_ID,
    MOCK_PANEL_NAME,
    MOCK_PANEL_PIN,
    MOCK_PASSWORD,
    MOCK_USERNAME,
)

CONF_POLLING = "polling"


def _has_error(errors):
    return errors is not None and len(errors.keys()) > 0


async def _bootstrap(
    hass,
    source=config_entries.SOURCE_USER,
    username=MOCK_USERNAME,
    password=MOCK_PASSWORD,
    panel_name=MOCK_PANEL_NAME,
    panel_pin=MOCK_PANEL_PIN,
) -> FlowResult:

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}
    )
    if result["type"] != data_entry_flow.RESULT_TYPE_FORM or _has_error(
        result["errors"]
    ):
        return result
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ELMAX_USERNAME: username,
            CONF_ELMAX_PASSWORD: password,
        },
    )
    if result2["type"] != data_entry_flow.RESULT_TYPE_FORM or _has_error(
        result2["errors"]
    ):
        return result2
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_ELMAX_PANEL_NAME: panel_name,
            CONF_ELMAX_PANEL_PIN: panel_pin,
        },
    )
    return result3


async def _reauth(hass):

    # Trigger reauth
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH},
        data={
            CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
            CONF_ELMAX_USERNAME: MOCK_USERNAME,
            CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
        },
    )
    if result2["type"] != data_entry_flow.RESULT_TYPE_FORM or _has_error(
        result2["errors"]
    ):
        return result2

    # Perform reauth confirm step
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
            CONF_ELMAX_USERNAME: MOCK_USERNAME,
            CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
        },
    )
    return result3


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_one_config_allowed(hass):
    """Test that only one Elmax configuration is allowed for each panel."""
    # Setup once.
    attempt1 = await _bootstrap(hass)
    assert attempt1["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    # Attempt to add another instance of the integration for the very same panel, it must fail.
    attempt2 = await _bootstrap(hass)
    assert attempt2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert attempt2["reason"] == "already_configured"


async def test_invalid_credentials(hass):
    """Test that invalid credentials throws an error."""
    with patch(
        "elmax_api.http.Elmax.login",
        side_effect=ElmaxBadLoginError(),
    ):
        result = await _bootstrap(
            hass, username="wrong_user_name@email.com", password="incorrect_password"
        )
        assert result["step_id"] == "user"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "bad_auth"}


async def test_connection_error(hass):
    """Test other than invalid credentials throws an error."""
    with patch(
        "elmax_api.http.Elmax.login",
        side_effect=ElmaxNetworkError(),
    ):
        result = await _bootstrap(
            hass, username="wrong_user_name@email.com", password="incorrect_password"
        )
        assert result["step_id"] == "user"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "network_error"}


async def test_unhandled_error(hass):
    """Test unhandled exceptions."""
    with patch(
        "elmax_api.http.Elmax.get_panel_status",
        side_effect=Exception(),
    ):
        result = await _bootstrap(hass)
        assert result["step_id"] == "panels"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown_error"}


async def test_invalid_pin(hass):
    """Test error is thrown when a wrong pin is used to pair a panel."""
    # Simulate bad pin response.
    with patch(
        "elmax_api.http.Elmax.get_panel_status",
        side_effect=ElmaxBadPinError(),
    ):
        result = await _bootstrap(hass)
        assert result["step_id"] == "panels"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "invalid_pin"}


async def test_no_online_panel(hass):
    """Test no-online panel is available."""
    # Simulate low-level api returns no panels.
    with patch(
        "elmax_api.http.Elmax.list_control_panels",
        return_value=[],
    ):
        result = await _bootstrap(hass)
        assert result["step_id"] == "user"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "no_panel_online"}


async def test_step_user(hass):
    """Test that the user step works."""
    result = await _bootstrap(hass)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
        CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
        CONF_ELMAX_USERNAME: MOCK_USERNAME,
        CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
    }


async def test_show_reauth(hass):
    """Test that the reauth form shows."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH},
        data={
            CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
            CONF_ELMAX_USERNAME: MOCK_USERNAME,
            CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_flow(hass):
    """Test that the reauth flow works."""
    # Simulate a first setup
    await _bootstrap(hass)
    # Trigger reauth
    result = await _reauth(hass)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_panel_disappeared(hass):
    """Test that the case where panel is no longer associated with the user."""
    # Simulate a first setup
    await _bootstrap(hass)
    # Trigger reauth
    with patch(
        "elmax_api.http.Elmax.list_control_panels",
        return_value=[],
    ):
        result = await _reauth(hass)
        assert result["step_id"] == "reauth_confirm"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "reauth_panel_disappeared"}


async def test_reauth_invalid_pin(hass):
    """Test that the case where panel is no longer associated with the user."""
    # Simulate a first setup
    await _bootstrap(hass)
    # Trigger reauth
    with patch(
        "elmax_api.http.Elmax.get_panel_status",
        side_effect=ElmaxBadPinError(),
    ):
        result = await _reauth(hass)
        assert result["step_id"] == "reauth_confirm"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "invalid_pin"}


async def test_reauth_bad_login(hass):
    """Test bad login attempt at reauth time."""
    # Simulate a first setup
    await _bootstrap(hass)
    # Trigger reauth
    with patch(
        "elmax_api.http.Elmax.login",
        side_effect=ElmaxBadLoginError(),
    ):
        result = await _reauth(hass)
        assert result["step_id"] == "reauth_confirm"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "bad_auth"}
