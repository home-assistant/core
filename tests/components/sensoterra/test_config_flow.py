"""Test the Sensoterra config flow."""

from unittest.mock import AsyncMock

from jwt import DecodeError
import pytest
from sensoterra.customerapi import InvalidAuth as StInvalidAuth, Timeout as StTimeout

from homeassistant.components.sensoterra.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import API_EMAIL, API_PASSWORD, API_TOKEN, HASS_UUID

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_customer_api_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    hass.data["core.uuid"] = HASS_UUID
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: API_EMAIL,
            CONF_PASSWORD: API_PASSWORD,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == API_EMAIL
    assert result["data"] == {
        CONF_TOKEN: API_TOKEN,
        CONF_EMAIL: API_EMAIL,
    }

    assert len(mock_customer_api_client.mock_calls) == 1


async def test_form_unique_id(
    hass: HomeAssistant, mock_customer_api_client: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    hass.data["core.uuid"] = HASS_UUID

    entry = MockConfigEntry(unique_id="39", domain=DOMAIN)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: API_EMAIL,
            CONF_PASSWORD: API_PASSWORD,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert len(mock_customer_api_client.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (StTimeout, "cannot_connect"),
        (StInvalidAuth("Invalid credentials"), "invalid_auth"),
        (DecodeError("Bad API token"), "invalid_access_token"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_customer_api_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle config form exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    hass.data["core.uuid"] = HASS_UUID

    mock_customer_api_client.get_token.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: API_EMAIL,
            CONF_PASSWORD: API_PASSWORD,
        },
    )
    assert result["errors"] == {"base": error}
    assert result["type"] is FlowResultType.FORM

    mock_customer_api_client.get_token.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: API_EMAIL,
            CONF_PASSWORD: API_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == API_EMAIL
    assert result["data"] == {
        CONF_TOKEN: API_TOKEN,
        CONF_EMAIL: API_EMAIL,
    }
    assert len(mock_customer_api_client.mock_calls) == 2
