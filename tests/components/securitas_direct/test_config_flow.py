"""Tests for the securitas direct config flow."""

from homeassistant import data_entry_flow, config_entries, setup
from homeassistant.components.securitas_direct import config_flow
from homeassistant.components.securitas_direct.const import (
    CONF_COUNTRY,
    CONF_INSTALLATION,
    CONF_LANG,
    DOMAIN,
    MULTI_SEC_CONFIGS,
    STEP_REAUTH,
    STEP_USER,
    UNABLE_TO_CONNECT,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from unittest.mock import patch
from tests.common import MockConfigEntry


def create_config_flow(hass):
    """Create a securitas direct config flow."""

    flow = config_flow.SecuritasConfigFlow()
    flow.hass = hass

    return flow


config = {
    CONF_USERNAME: "user1",
    CONF_PASSWORD: "password",
    CONF_INSTALLATION: "123",
    CONF_COUNTRY: "PT",
    CONF_LANG: "pt",
    CONF_CODE: 123,
}


async def test_show_form(hass):
    """Test that the form is served with no input."""

    flow = create_config_flow(hass)
    result = await flow.async_step_user(user_input=None)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == STEP_USER


async def test_multiple_config(hass):
    """Test multiple configurations."""

    flow = create_config_flow(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data=config,
    ).add_to_hass(hass)

    step_user_result = await flow.async_step_user()
    assert step_user_result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert step_user_result["reason"] == MULTI_SEC_CONFIGS


async def test_invalid_connection(hass):
    """Test that invalid connection."""

    flow = create_config_flow(hass)
    result = await flow.async_step_user(config)
    assert result["errors"] == {"base": UNABLE_TO_CONNECT}


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "securitas_direct", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch("homeassistant.components.securitas_direct.config_flow.Session"), patch(
        "homeassistant.components.securitas_direct.Session"
    ), patch(
        "homeassistant.components.securitas_direct.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "123"
    assert result2["data"] == config
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth(hass):
    """Test re-authentication."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id=config[CONF_INSTALLATION],
        data=config,
    ).add_to_hass(hass)

    with patch("homeassistant.components.securitas_direct.config_flow.Session"), patch(
        "homeassistant.components.securitas_direct.Session"
    ), patch("homeassistant.components.securitas_direct.Installation"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH},
            data=config,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == STEP_REAUTH
        assert len(hass.config_entries.async_entries()) == 1
