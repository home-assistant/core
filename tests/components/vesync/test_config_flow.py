"""Test for vesync config flow."""

from unittest.mock import patch

from homeassistant.components.vesync import DOMAIN, config_flow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_abort_already_setup(hass: HomeAssistant) -> None:
    """Test if we abort because component is already setup."""
    flow = config_flow.VeSyncFlowHandler()
    flow.hass = hass
    MockConfigEntry(domain=DOMAIN, title="user", data={"user": "pass"}).add_to_hass(
        hass
    )
    result = await flow.async_step_user()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_invalid_login_error(hass: HomeAssistant) -> None:
    """Test if we return error for invalid username and password."""
    test_dict = {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    flow = config_flow.VeSyncFlowHandler()
    flow.hass = hass
    with patch("pyvesync.vesync.VeSync.login", return_value=False):
        result = await flow.async_step_user(user_input=test_dict)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_config_flow_user_input(hass: HomeAssistant) -> None:
    """Test config flow with user input."""
    flow = config_flow.VeSyncFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.FORM
    with patch("pyvesync.vesync.VeSync.login", return_value=True):
        result = await flow.async_step_user(
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_USERNAME] == "user"
        assert result["data"][CONF_PASSWORD] == "pass"
