"""Test the fyta config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.fyta import config_flow
from homeassistant.components.fyta.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

USERNAME = "fyta_user"
PASSWORD = "fyta_pass"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.fyta.config_flow.validate_input",
        return_value={"title": USERNAME},
    ), patch(
        "homeassistant.components.fyta.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == USERNAME
    assert result2["data"] == {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.fixture(name="validate_input")
def mock_controller():
    """Mock a successful _host_in_configuration_exists."""
    with patch(
        "homeassistant.components.solarlog.config_flow.validate_input",
        return_value={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    ):
        yield


def init_config_flow(hass: HomeAssistant):
    """Init a configuration flow."""
    flow = config_flow.FytaConfigFlow()
    flow.hass = hass
    return flow


async def test_user(hass: HomeAssistant) -> None:
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # tests with all information provided
    with patch(
        "homeassistant.components.fyta.config_flow.validate_input",
        return_value={"title": USERNAME},
    ):
        result = await flow.async_step_user(
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauthentification."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.fyta.config_flow.validate_input",
        return_value={"title": USERNAME},
    ):
        result = await flow.async_step_reauth_confirm(
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
