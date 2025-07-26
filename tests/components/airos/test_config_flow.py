"""Test the Ubiquiti airOS config flow."""

from typing import Any
from unittest.mock import AsyncMock

from airos.exceptions import (
    ConnectionAuthenticationError,
    DeviceConnectionError,
    KeyDataMissingError,
)
import pytest

from homeassistant.components.airos.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

MOCK_CONFIG = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


async def test_form_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airos_client: AsyncMock,
    ap_fixture: dict[str, Any],
) -> None:
    """Test we get the form and create the appropriate entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NanoStation 5AC ap name"
    assert result["result"].unique_id == "03aa0d0b40fed0a47088293584ef5432"
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1

    # Test we can't re-add existing device
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        MOCK_CONFIG,
    )

    assert result2["type"] is FlowResultType.ABORT


@pytest.mark.parametrize(
    ("mock_airos_client", "expected_base"),
    [
        (ConnectionAuthenticationError, "invalid_auth"),
        (DeviceConnectionError, "cannot_connect"),
        (KeyDataMissingError, "key_data_missing"),
        (Exception, "unknown"),
    ],
    indirect=["mock_airos_client"],
)
async def test_form_exception_handling(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airos_client: AsyncMock,
    ap_fixture: dict[str, Any],
    expected_base: str,
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_base}

    mock_airos_client.login.side_effect = None
    mock_airos_client.login.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NanoStation 5AC ap name"
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1
