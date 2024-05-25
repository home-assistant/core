"""Define tests for the The Things Network onfig flows."""

import pytest
from ttn_client import TTNAuthError

from homeassistant.components.thethingsnetwork.const import (
    CONF_API_KEY,
    CONF_APP_ID,
    CONF_HOSTNAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import API_KEY, APP_ID, HOSTNAME, init_integration

USER_DATA = {CONF_HOSTNAME: HOSTNAME, CONF_APP_ID: APP_ID, CONF_API_KEY: API_KEY}


async def test_user(hass: HomeAssistant, mock_ttnclient) -> None:
    """Test user config."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == APP_ID
    assert result["data"][CONF_HOSTNAME] == HOSTNAME
    assert result["data"][CONF_APP_ID] == APP_ID
    assert result["data"][CONF_API_KEY] == API_KEY


@pytest.mark.parametrize(
    ("fetch_data_exceptiom", "base_error"),
    [(TTNAuthError, "invalid_auth"), (Exception, "unknown")],
)
async def test_user_erors(
    hass: HomeAssistant, fetch_data_exceptiom, base_error, mock_ttnclient
) -> None:
    """Test user config errors."""

    # Set client fetch data mock
    mock_fetch_data_exceptiom = None

    def mock_fetch_data():
        if mock_fetch_data_exceptiom:
            raise mock_fetch_data_exceptiom

    mock_ttnclient.return_value.fetch_data.side_effect = mock_fetch_data

    # Test error
    mock_fetch_data_exceptiom = fetch_data_exceptiom
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert base_error in result["errors"]["base"]

    # Recover
    mock_fetch_data_exceptiom = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_DATA,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_step_reauth(
    hass: HomeAssistant, mock_ttnclient, mock_config_entry
) -> None:
    """Test that the reauth step works."""

    await init_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": APP_ID,
            "entry_id": mock_config_entry.entry_id,
        },
        data=USER_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    new_api_key = "1234"
    new_user_input = dict(USER_DATA)
    new_user_input[CONF_API_KEY] = new_api_key

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=new_user_input
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    assert hass.config_entries.async_entries()[0].data[CONF_API_KEY] == new_api_key
    await hass.async_block_till_done()
