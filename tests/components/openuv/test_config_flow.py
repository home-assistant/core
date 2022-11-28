"""Define tests for the OpenUV config flow."""
from unittest.mock import patch

from pyopenuv.errors import InvalidApiKeyError
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


async def test_duplicate_error(hass, config, config_entry):
    """Test that errors are shown when duplicates are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_api_key(hass, config):
    """Test that an invalid API key throws an error."""
    with patch(
        "homeassistant.components.openuv.Client.uv_index",
        side_effect=InvalidApiKeyError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=config
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


def _get_schema_marker(data_schema: vol.Schema, key: str) -> vol.Marker:
    for k in data_schema.schema:
        if k == key and isinstance(k, vol.Marker):
            return k
    return None


async def test_options_flow(hass, config_entry):
    """Test config flow options."""
    with patch("homeassistant.components.openuv.async_setup_entry", return_value=True):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        # Original schema uses defaults for suggested values
        assert _get_schema_marker(
            result["data_schema"], CONF_FROM_WINDOW
        ).description == {"suggested_value": 3.5}
        assert _get_schema_marker(
            result["data_schema"], CONF_TO_WINDOW
        ).description == {"suggested_value": 3.5}

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_FROM_WINDOW: 3.5, CONF_TO_WINDOW: 2.0}
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert config_entry.options == {CONF_FROM_WINDOW: 3.5, CONF_TO_WINDOW: 2.0}

        # Subsequent schema uses previous input for suggested values
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        assert _get_schema_marker(
            result["data_schema"], CONF_FROM_WINDOW
        ).description == {"suggested_value": 3.5}
        assert _get_schema_marker(
            result["data_schema"], CONF_TO_WINDOW
        ).description == {"suggested_value": 2.0}


async def test_step_reauth(hass, config, config_entry, setup_openuv):
    """Test that the reauth step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH}, data=config
    )
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch("homeassistant.components.openuv.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "new_api_key"}
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1


async def test_step_user(hass, config, setup_openuv):
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "51.528308, -0.3817765"
    assert result["data"] == {
        CONF_API_KEY: "abcde12345",
        CONF_ELEVATION: 0,
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }
