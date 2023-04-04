"""Define tests for the NextDNS config flow."""
import asyncio
from unittest.mock import patch

from nextdns import ApiError, InvalidApiKeyError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.nextdns.const import (
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import PROFILES, init_integration


async def test_form_create_entry(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nextdns.NextDns.get_profiles", return_value=PROFILES
    ), patch(
        "homeassistant.components.nextdns.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "fake_api_key"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "profiles"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PROFILE_NAME: "Fake Profile"}
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fake Profile"
    assert result["data"][CONF_API_KEY] == "fake_api_key"
    assert result["data"][CONF_PROFILE_ID] == "xyz12"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (ApiError("API Error"), "cannot_connect"),
        (InvalidApiKeyError, "invalid_api_key"),
        (asyncio.TimeoutError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant, exc: Exception, base_error: str
) -> None:
    """Test we handle errors."""
    with patch(
        "homeassistant.components.nextdns.NextDns.get_profiles", side_effect=exc
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_API_KEY: "fake_api_key"},
        )

    assert result["errors"] == {"base": base_error}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test that errors are shown when duplicates are added."""
    await init_integration(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nextdns.NextDns.get_profiles", return_value=PROFILES
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "fake_api_key"},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PROFILE_NAME: "Fake Profile"}
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
