"""Test Anova config flow."""

from unittest.mock import patch

from pyanglianwater.exceptions import InvalidPasswordError, InvalidUsernameError

from homeassistant import config_entries
from homeassistant.components.anglian_water.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG_DATA


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "sample@gmail.com"
    assert result["data"] == MOCK_CONFIG_DATA


async def test_flow_wrong_login(hass: HomeAssistant) -> None:
    """Test incorrect login throwing error."""
    with patch(
        "homeassistant.components.anglian_water.config_flow.API.create_via_login",
        side_effect=(InvalidUsernameError, InvalidPasswordError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_CONFIG_DATA,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error throwing error."""
    with patch(
        "homeassistant.components.anglian_water.config_flow.API.create_via_login",
        side_effect=Exception(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_CONFIG_DATA,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}
