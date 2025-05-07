"""Tests for the Amazon Devices config flow."""

from unittest.mock import AsyncMock

from aioamazondevices import CannotAuthenticate, CannotConnect
import pytest

from homeassistant.components.amazon_devices.const import CONF_LOGIN_DATA, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "IT",
            CONF_USERNAME: "test",
            CONF_PASSWORD: "test",
            CONF_CODE: 123123,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"] == {
        CONF_COUNTRY: "IT",
        CONF_USERNAME: "test",
        CONF_PASSWORD: "test",
        CONF_LOGIN_DATA: {
            "customer_info": {"user_id": "test"},
        },
    }
    assert result["result"].unique_id == "test"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (CannotConnect, "cannot_connect"),
        (CannotAuthenticate, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test flow errors."""
    mock_amazon_devices_client.login_mode_interactive.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "IT",
            CONF_USERNAME: "test",
            CONF_PASSWORD: "test",
            CONF_CODE: 123123,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_amazon_devices_client.login_mode_interactive.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "IT",
            CONF_USERNAME: "test",
            CONF_PASSWORD: "test",
            CONF_CODE: 123123,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: "IT",
            CONF_USERNAME: "test",
            CONF_PASSWORD: "test",
            CONF_CODE: 123123,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
