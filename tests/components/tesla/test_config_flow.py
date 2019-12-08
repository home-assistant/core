"""Test the Tesla config flow."""
from unittest.mock import Mock, patch

from teslajsonpy import TeslaException

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.tesla import config_flow
from homeassistant.components.tesla.const import DOMAIN
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)

from tests.common import mock_coro


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.tesla.config_flow.TeslaAPI.connect",
        return_value=mock_coro(("test-refresh-token", "test-access-token")),
    ), patch(
        "homeassistant.components.tesla.async_setup", return_value=mock_coro(True)
    ) as mock_setup, patch(
        "homeassistant.components.tesla.async_setup_entry", return_value=mock_coro(True)
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "test", CONF_USERNAME: "test@email.com"}
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "test@email.com"
    assert result2["data"] == {
        "token": "test-refresh-token",
        "access_token": "test-access-token",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tesla.config_flow.TeslaAPI.connect",
        side_effect=TeslaException(401),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_credentials"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tesla.config_flow.TeslaAPI.connect",
        side_effect=TeslaException(code=404),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "test", CONF_USERNAME: "test@email.com"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "connection_error"}


async def test_import(hass):
    """Test import step."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.tesla.config_flow.TeslaAPI.connect",
        return_value=mock_coro(("test-refresh-token", "test-access-token")),
    ):
        result = await flow.async_step_import(
            {CONF_PASSWORD: "test", CONF_USERNAME: "test@email.com"}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test@email.com"
    assert result["data"][CONF_ACCESS_TOKEN] == "test-access-token"
    assert result["data"][CONF_TOKEN] == "test-refresh-token"
    assert result["description_placeholders"] is None


def init_config_flow(hass):
    """Init a configuration flow."""
    hass.config.api = Mock()
    flow = config_flow.TeslaConfigFlow()
    flow.hass = hass
    return flow
