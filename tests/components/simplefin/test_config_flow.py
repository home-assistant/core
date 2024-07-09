"""Test config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from simplefin4py.exceptions import (
    SimpleFinAuthError,
    SimpleFinClaimError,
    SimpleFinInvalidAccountURLError,
    SimpleFinInvalidClaimTokenError,
    SimpleFinPaymentRequiredError,
)

from homeassistant.components.simplefin import CONF_ACCESS_URL
from homeassistant.components.simplefin.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_successful_claim(
    hass: HomeAssistant,
    mock_simplefin_client: AsyncMock,
) -> None:
    """Test successful token claim in config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.simplefin.config_flow.SimpleFin.claim_setup_token",
        return_value="https://i:am@yomama.house.com",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ACCESS_URL: "donJulio"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_access_url(
    hass: HomeAssistant,
    mock_simplefin_client: AsyncMock,
) -> None:
    """Test standard config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCESS_URL: "http://user:password@string"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ACCESS_URL] == "http://user:password@string"
    assert result["title"] == "SimpleFIN"


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (SimpleFinInvalidAccountURLError, "url_error"),
        (SimpleFinPaymentRequiredError, "payment_required"),
        (SimpleFinAuthError, "invalid_auth"),
    ],
)
async def test_access_url_errors(
    hass: HomeAssistant,
    mock_simplefin_client: AsyncMock,
    side_effect: Exception,
    error_key: str,
) -> None:
    """Test the various errors we can get in access_url mode."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.simplefin.config_flow.SimpleFin.claim_setup_token",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ACCESS_URL: "donJulio"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error_key}

    # Pass the entry creation
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCESS_URL: "http://user:password@string"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ACCESS_URL: "http://user:password@string"}
    assert result["title"] == "SimpleFIN"


@pytest.mark.parametrize(
    "side_effect, error_key",  # noqa: PT006
    [
        (SimpleFinInvalidClaimTokenError, "invalid_claim_token"),
        (SimpleFinClaimError, "claim_error"),
    ],
)
async def test_claim_token_errors(
    hass: HomeAssistant, mock_simplefin_client: AsyncMock, side_effect, error_key
) -> None:
    """Test config flow with various token claim errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.simplefin.config_flow.SimpleFin.claim_setup_token",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ACCESS_URL: "donJulio"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error_key}

    # Finally succeed in creating the item
    with patch(
        "homeassistant.components.simplefin.config_flow.SimpleFin.claim_setup_token",
        return_value="https://i:am@yomama.house.com",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ACCESS_URL: "donJulio"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {CONF_ACCESS_URL: "https://i:am@yomama.house.com"}
        assert result["title"] == "SimpleFIN"
