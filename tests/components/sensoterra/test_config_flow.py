"""Test the Sensoterra config flow."""

from enum import Enum
from unittest.mock import AsyncMock, patch

import pytest
from sensoterra.customerapi import InvalidAuth as StInvalidAuth, Timeout as StTimeout

from homeassistant.components.sensoterra.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import API_EMAIL, API_PASSWORD, API_TOKEN, HASS_UUID, SOURCE_USER

Test = Enum("Test", ["INVALID_AUTH", "TIMEOUT"])


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
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
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("test", [Test.INVALID_AUTH, Test.TIMEOUT])
async def test_form_various(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, test: Test
) -> None:
    """Test we handle invalid auth and connection failures."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    hass.data["core.uuid"] = HASS_UUID

    match test:
        case Test.TIMEOUT:
            with patch(
                "sensoterra.customerapi.CustomerApi.get_token",
                side_effect=StTimeout,
            ):
                result = await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    {
                        CONF_EMAIL: API_EMAIL,
                        CONF_PASSWORD: API_PASSWORD,
                    },
                )
            assert result["errors"] == {"base": "cannot_connect"}

        case Test.INVALID_AUTH:
            with patch(
                "sensoterra.customerapi.CustomerApi.get_token",
                side_effect=StInvalidAuth("Invalid credentials"),
            ):
                result = await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    {
                        CONF_EMAIL: API_EMAIL,
                        CONF_PASSWORD: API_PASSWORD,
                    },
                )
            assert result["errors"] == {"base": "invalid_auth"}

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
    assert len(mock_setup_entry.mock_calls) == 1
