"""Test the Sensoterra config flow."""

from unittest.mock import AsyncMock, patch

from sensoterra.customerapi import InvalidAuth as StInvalidAuth, Timeout as StTimeout

from homeassistant import config_entries
from homeassistant.components.sensoterra.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

API_ACCESS_TOKEN = "api_token"
API_EMAIL = "test-email@example.com"
API_PASSWORD = "test-password"
HASS_UUID = "phony-unique-id"


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    hass.data["core.uuid"] = HASS_UUID

    with patch(
        "sensoterra.customerapi.CustomerApi.get_token",
        return_value=API_ACCESS_TOKEN,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: API_EMAIL,
                CONF_PASSWORD: API_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == API_EMAIL
    assert result["data"] == {
        CONF_TOKEN: API_ACCESS_TOKEN,
        CONF_EMAIL: API_EMAIL,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    hass.data["core.uuid"] = HASS_UUID

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

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "sensoterra.customerapi.CustomerApi.get_token",
        return_value=API_ACCESS_TOKEN,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: API_EMAIL,
                CONF_PASSWORD: API_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == API_EMAIL
    assert result["data"] == {
        CONF_TOKEN: API_ACCESS_TOKEN,
        CONF_EMAIL: API_EMAIL,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    hass.data["core.uuid"] = HASS_UUID

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

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "sensoterra.customerapi.CustomerApi.get_token",
        return_value=API_ACCESS_TOKEN,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: API_EMAIL,
                CONF_PASSWORD: API_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == API_EMAIL
    assert result["data"] == {
        CONF_EMAIL: API_EMAIL,
        CONF_TOKEN: API_ACCESS_TOKEN,
    }
    assert len(mock_setup_entry.mock_calls) == 1
