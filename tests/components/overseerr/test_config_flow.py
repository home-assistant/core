"""Test the Overseerr config flow."""
from unittest.mock import AsyncMock, patch

import pytest
import requests_mock
from urllib3.exceptions import MaxRetryError

from homeassistant import config_entries
from homeassistant.components.overseerr.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

USER_INPUT = {CONF_URL: "http://localhost:5055/api/v1", CONF_API_KEY: "test-api-key"}

YAML_IMPORT = {CONF_URL: "http://localhost:5055/api/v1", CONF_API_KEY: "test-api-key"}


@patch("overseerr_api.Configuration")
@patch("overseerr_api.ApiClient")
@patch("overseerr_api.AuthApi")
async def test_flow_user(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test flow with connection failure, fail with cannot_connect
    with requests_mock.Mocker() as mock:
        mock.get(
            f"{USER_INPUT[CONF_URL]}/api/v1/auth/me",
            exc=MaxRetryError,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "open_api_exception"}


async def test_form(hass: HomeAssistant, mock_api: requests_mock.Mocker) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with requests_mock.Mocker() as mock:
        mock.get(
            f"{USER_INPUT[CONF_URL]}/auth/me",
            exc=MaxRetryError,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Overseerr"
    assert result["data"] == {
        CONF_URL: USER_INPUT[CONF_URL],
        CONF_API_KEY: USER_INPUT[CONF_API_KEY],
    }


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with requests_mock.Mocker() as mock:
        mock.get(
            f"{USER_INPUT[CONF_URL]}/auth/me",
            exc=MaxRetryError,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["title"] == "Overseerr"
    assert result["data"] == {
        CONF_URL: USER_INPUT[CONF_URL],
        CONF_API_KEY: USER_INPUT[CONF_API_KEY],
    }

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "homeassistant.components.overseerr.config_flow.PlaceholderHub.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: USER_INPUT[CONF_URL],
                CONF_API_KEY: USER_INPUT[CONF_API_KEY],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == {
        CONF_URL: USER_INPUT[CONF_URL],
        CONF_API_KEY: USER_INPUT[CONF_API_KEY],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.overseerr.config_flow.PlaceholderHub.authenticate",
        side_effect=MaxRetryError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: USER_INPUT[CONF_URL],
                CONF_API_KEY: USER_INPUT[CONF_API_KEY],
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.overseerr.config_flow.PlaceholderHub.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: USER_INPUT[CONF_URL],
                CONF_API_KEY: USER_INPUT[CONF_API_KEY],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == {
        CONF_URL: USER_INPUT[CONF_URL],
        CONF_API_KEY: USER_INPUT[CONF_API_KEY],
    }
    assert len(mock_setup_entry.mock_calls) == 1
