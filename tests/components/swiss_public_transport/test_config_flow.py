"""Test the swiss_public_transport config flow."""
import pytest

from homeassistant.components.swiss_public_transport import config_flow
from homeassistant.components.swiss_public_transport.const import (
    CONF_DESTINATION,
    CONF_START,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_flow_user_init(hass: HomeAssistant):
    """Test the initialization of the form in the first step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["handler"] == "swiss_public_transport"
    assert result["data_schema"] == config_flow.DATA_SCHEMA


async def test_flow_user_init_data(hass: HomeAssistant):
    """Test errors populated when auth token is invalid."""
    _result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        _result["flow_id"],
        user_input={
            CONF_NAME: "test_name",
            CONF_START: "test_start",
            CONF_DESTINATION: "test_destination",
        },
    )

    assert result["type"] == "create_entry"

    assert {
        CONF_NAME: "test_name",
        CONF_START: "test_start",
        CONF_DESTINATION: "test_destination",
    } == result["data"]
