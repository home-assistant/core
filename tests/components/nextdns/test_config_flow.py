"""Define tests for the NextDNS config flow."""

from unittest.mock import AsyncMock, patch

from nextdns import ApiError, InvalidApiKeyError
import pytest
from tenacity import RetryError

from homeassistant.components.nextdns.const import CONF_PROFILE_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_PROFILE_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import init_integration

from tests.common import MockConfigEntry


async def test_form_create_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "fake_api_key"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "profiles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PROFILE_NAME: "Fake Profile"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fake Profile"
    assert result["data"][CONF_API_KEY] == "fake_api_key"
    assert result["data"][CONF_PROFILE_ID] == "xyz12"
    assert result["result"].unique_id == "xyz12"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (ApiError("API Error"), "cannot_connect"),
        (InvalidApiKeyError, "invalid_api_key"),
        (RetryError("Retry Error"), "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_nextdns_client: AsyncMock,
    exc: Exception,
    base_error: str,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nextdns.NextDns.create",
        side_effect=exc,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "fake_api_key"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base_error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "fake_api_key"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "profiles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PROFILE_NAME: "Fake Profile"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fake Profile"
    assert result["data"][CONF_API_KEY] == "fake_api_key"
    assert result["data"][CONF_PROFILE_ID] == "xyz12"
    assert result["result"].unique_id == "xyz12"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test that errors are shown when duplicates are added."""
    await init_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "fake_api_key"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PROFILE_NAME: "Fake Profile"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_successful(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test starting a reauthentication flow."""
    await init_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (ApiError("API Error"), "cannot_connect"),
        (InvalidApiKeyError, "invalid_api_key"),
        (RetryError("Retry Error"), "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    exc: Exception,
    base_error: str,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test reauthentication flow with errors."""
    await init_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch("homeassistant.components.nextdns.NextDns.create", side_effect=exc):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "new_api_key"},
        )

    assert result["errors"] == {"base": base_error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
