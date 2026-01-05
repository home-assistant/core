"""Tests for the Overseerr config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from python_overseerr.exceptions import (
    OverseerrAuthenticationError,
    OverseerrConnectionError,
)

from homeassistant.components.overseerr.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_WEBHOOK_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import WEBHOOK_ID

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def patch_webhook_id() -> None:
    """Patch webhook ID generation."""
    with patch(
        "homeassistant.components.overseerr.config_flow.async_generate_id",
        return_value=WEBHOOK_ID,
    ):
        yield


async def test_full_flow(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
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
        {CONF_URL: "http://overseerr.test", CONF_API_KEY: "test-key"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Overseerr"
    assert result["data"] == {
        CONF_HOST: "overseerr.test",
        CONF_PORT: 80,
        CONF_SSL: False,
        CONF_API_KEY: "test-key",
        CONF_WEBHOOK_ID: "test-webhook-id",
    }


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (OverseerrAuthenticationError, "invalid_auth"),
        (OverseerrConnectionError, "cannot_connect"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test flow errors."""
    mock_overseerr_client.get_request_count.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://overseerr.test", CONF_API_KEY: "test-key"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_overseerr_client.get_request_count.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://overseerr.test", CONF_API_KEY: "test-key"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_invalid_host(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test flow invalid host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://", CONF_API_KEY: "test-key"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"url": "invalid_host"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://overseerr.test", CONF_API_KEY: "test-key"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
    hass: HomeAssistant,
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
        {CONF_URL: "http://overseerr.test", CONF_API_KEY: "test-key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new-test-key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry.data[CONF_API_KEY] == "new-test-key"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (OverseerrAuthenticationError, "invalid_auth"),
        (OverseerrConnectionError, "cannot_connect"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_overseerr_client.get_request_count.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new-test-key"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_overseerr_client.get_request_count.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new-test-key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry.data[CONF_API_KEY] == "new-test-key"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://overseerr2.test", CONF_API_KEY: "new-key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "overseerr2.test",
        CONF_PORT: 80,
        CONF_SSL: False,
        CONF_API_KEY: "new-key",
        CONF_WEBHOOK_ID: WEBHOOK_ID,
    }


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (OverseerrAuthenticationError, "invalid_auth"),
        (OverseerrConnectionError, "cannot_connect"),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test reconfigure flow errors."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_overseerr_client.get_request_count.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://overseerr2.test", CONF_API_KEY: "new-key"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_overseerr_client.get_request_count.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://overseerr2.test", CONF_API_KEY: "new-key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
