"""Test the Sensoterra config flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

from jwt import DecodeError, decode
import pytest
from sensoterra.customerapi import InvalidAuth as StInvalidAuth, Timeout as StTimeout

from homeassistant.components.sensoterra.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import API_EMAIL, API_PASSWORD, API_TOKEN, HASS_UUID, SOURCE_USER

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_get_token: AsyncMock) -> None:
    """Test we get the form."""
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

    assert len(mock_get_token.mock_calls) == 1


async def test_form_unique_id(hass: HomeAssistant, mock_get_token: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    hass.data["core.uuid"] = HASS_UUID

    # Add a ConfigEntry with the same unique_id as the API_TOKEN contains.
    decoded_token = decode(
        API_TOKEN, algorithms=["HS256"], options={"verify_signature": False}
    )
    entry = MockConfigEntry(unique_id=decoded_token["sub"], domain=DOMAIN)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: API_EMAIL,
            CONF_PASSWORD: API_PASSWORD,
        },
    )
    assert result["type"] is FlowResultType.ABORT

    assert len(mock_get_token.mock_calls) == 1


@pytest.mark.parametrize(
    "test_input",
    [
        (StTimeout, "cannot_connect"),
        (StInvalidAuth("Invalid credentials"), "invalid_auth"),
        (DecodeError("Bad API token"), "invalid_access_token"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    # mock_setup_entry: AsyncMock,
    mock_get_token: AsyncMock,
    test_input: tuple[Any, str],
) -> None:
    """Test we handle config form exceptions."""
    (exception, error_code) = test_input

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    hass.data["core.uuid"] = HASS_UUID

    with patch(
        "sensoterra.customerapi.CustomerApi.get_token",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: API_EMAIL,
                CONF_PASSWORD: API_PASSWORD,
            },
        )
    assert result["errors"] == {"base": error_code}
    assert result["type"] is FlowResultType.FORM

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
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
    assert len(mock_get_token.mock_calls) == 1
