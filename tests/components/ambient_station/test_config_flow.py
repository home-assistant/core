"""Define tests for the Ambient PWS config flow."""
from unittest.mock import AsyncMock

from aioambient.errors import AmbientError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.ambient_station import CONF_APP_KEY, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY


async def test_duplicate_error(hass, config, config_entry, setup_ambient_station):
    """Test that errors are shown when duplicates are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "devices,error",
    [
        (AmbientError, "invalid_key"),
        (AsyncMock(return_value=[]), "no_devices"),
    ],
)
async def test_errors(hass, config, devices, error, setup_ambient_station):
    """Test that various issues show the correct error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_user(hass, config, setup_ambient_station):
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "67890fghij67"
    assert result["data"] == {
        CONF_API_KEY: "12345abcde12345abcde",
        CONF_APP_KEY: "67890fghij67890fghij",
    }
