"""Define tests for the OpenUV config flow."""
from unittest.mock import AsyncMock, patch

from pyopenuv.errors import InvalidApiKeyError
import pytest
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.openuv import CONF_FROM_WINDOW, CONF_TO_WINDOW, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant

from .conftest import TEST_API_KEY, TEST_ELEVATION, TEST_LATITUDE, TEST_LONGITUDE

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_create_entry(hass: HomeAssistant, client, config, mock_pyopenuv) -> None:
    """Test creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test an error occurring:
    with patch.object(client, "uv_index", AsyncMock(side_effect=InvalidApiKeyError)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=config
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}

    # Test that we can recover from the error:
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_LATITUDE}, {TEST_LONGITUDE}"
    assert result["data"] == {
        CONF_API_KEY: TEST_API_KEY,
        CONF_ELEVATION: TEST_ELEVATION,
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
    }


async def test_duplicate_error(
    hass: HomeAssistant, config, config_entry, setup_config_entry
) -> None:
    """Test that errors are shown when duplicates are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test config flow options."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    def get_schema_marker(data_schema: vol.Schema, key: str) -> vol.Marker:
        for k in data_schema.schema:
            if k == key and isinstance(k, vol.Marker):
                return k
        return None

    # Original schema uses defaults for suggested values:
    assert get_schema_marker(result["data_schema"], CONF_FROM_WINDOW).description == {
        "suggested_value": 3.5
    }
    assert get_schema_marker(result["data_schema"], CONF_TO_WINDOW).description == {
        "suggested_value": 3.5
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_FROM_WINDOW: 3.5, CONF_TO_WINDOW: 2.0}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_FROM_WINDOW: 3.5, CONF_TO_WINDOW: 2.0}

    # Subsequent schema uses previous input for suggested values:
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    assert get_schema_marker(result["data_schema"], CONF_FROM_WINDOW).description == {
        "suggested_value": 3.5
    }
    assert get_schema_marker(result["data_schema"], CONF_TO_WINDOW).description == {
        "suggested_value": 2.0
    }


async def test_step_reauth(
    hass: HomeAssistant, config, config_entry, setup_config_entry
) -> None:
    """Test that the reauth step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH}, data=config
    )
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_api_key"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1
