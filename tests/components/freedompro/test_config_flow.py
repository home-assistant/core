"""Define tests for the Freedompro config flow."""

from unittest.mock import patch

import pytest

from homeassistant.components.freedompro.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import DEVICES

VALID_CONFIG = {
    CONF_API_KEY: "ksdjfgslkjdfksjdfksjgfksjd",
}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test that errors are shown when API key is invalid."""
    with patch(
        "homeassistant.components.freedompro.config_flow.get_list",
        return_value={
            "state": False,
            "code": -201,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["errors"] == {"base": "invalid_auth"}


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when API key is invalid."""
    with patch(
        "homeassistant.components.freedompro.config_flow.get_list",
        return_value={
            "state": False,
            "code": -200,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["errors"] == {"base": "cannot_connect"}


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    with patch(
        "homeassistant.components.freedompro.config_flow.get_list",
        return_value={
            "state": True,
            "devices": DEVICES,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Freedompro"
        assert result["data"][CONF_API_KEY] == "ksdjfgslkjdfksjdfksjgfksjd"
