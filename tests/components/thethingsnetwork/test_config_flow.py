"""Define tests for the The Things Network onfig flows."""

from ttn_client import TTNAuthError

from homeassistant.components.thethingsnetwork.const import (
    CONF_API_KEY,
    CONF_APP_ID,
    CONF_HOSTNAME,
    DOMAIN,
    TTN_API_HOSTNAME,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import add_schema_suggestion
from .conftest import API_KEY, APP_ID, CONFIG_ENTRY, HOSTNAME

USER_DATA = {CONF_HOSTNAME: HOSTNAME, CONF_APP_ID: APP_ID, CONF_API_KEY: API_KEY}
USER_DATA_PARTIAL = {CONF_APP_ID: APP_ID, CONF_API_KEY: API_KEY}


async def test_user(hass: HomeAssistant, mock_TTNClient) -> None:
    """Test user config."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    schema = result["data_schema"]
    user_data = schema(add_schema_suggestion(schema.schema, USER_DATA_PARTIAL))
    assert user_data[CONF_HOSTNAME] == TTN_API_HOSTNAME  # Default value

    user_data[CONF_HOSTNAME] = HOSTNAME  # Change default value

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_data,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == APP_ID
    assert result["data"][CONF_HOSTNAME] == HOSTNAME
    assert result["data"][CONF_APP_ID] == APP_ID
    assert result["data"][CONF_API_KEY] == API_KEY

    # Prepare to test errors
    user_data[CONF_APP_ID] = "another app"
    mock_fetch_data_exceptiom = None

    def mock_fetch_data():
        if mock_fetch_data_exceptiom:
            raise mock_fetch_data_exceptiom

    mock_TTNClient.return_value.fetch_data.side_effect = mock_fetch_data

    # Connection error
    mock_fetch_data_exceptiom = TTNAuthError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Unknown error
    mock_fetch_data_exceptiom = Exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_data,
    )
    assert result["type"] == FlowResultType.FORM
    assert "unknown" in result["errors"]["base"]

    # Recover
    mock_fetch_data_exceptiom = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_data,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_step_reauth(
    hass: HomeAssistant, mock_TTNClient, init_integration
) -> None:
    """Test that the reauth step works."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": APP_ID,
            "entry_id": CONFIG_ENTRY.entry_id,
        },
        data=USER_DATA,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    schema = result["data_schema"]
    user_data = schema(add_schema_suggestion(schema.schema, {}))
    assert user_data[CONF_API_KEY] == API_KEY  # Default value
    new_api_key = "1234"
    user_data[CONF_API_KEY] = new_api_key  # Change default value

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_data
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    assert hass.config_entries.async_entries()[0].data[CONF_API_KEY] == new_api_key
    await hass.async_block_till_done()
