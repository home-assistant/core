"""Test the Splunk config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.splunk.const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SSL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_flow_success(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: "test-token-123",
            CONF_HOST: "splunk.example.com",
            CONF_PORT: 8088,
            CONF_SSL: True,
            CONF_NAME: "Test Splunk",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Splunk"
    assert result["data"] == {
        CONF_TOKEN: "test-token-123",
        CONF_HOST: "splunk.example.com",
        CONF_PORT: 8088,
        CONF_SSL: True,
        "verify_ssl": True,
        CONF_NAME: "Test Splunk",
    }
    assert result["result"].unique_id == "splunk.example.com:8088"

    # Verify that check was called twice (connectivity and token)
    assert mock_hass_splunk.check.call_count == 2


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test user flow with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock connectivity check failure
    mock_hass_splunk.check.side_effect = [False, True]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: "test-token-123",
            CONF_HOST: "splunk.example.com",
            CONF_PORT: 8088,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test user flow with invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock connectivity ok but token check fails
    mock_hass_splunk.check.side_effect = [True, False]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: "invalid-token",
            CONF_HOST: "splunk.example.com",
            CONF_PORT: 8088,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_unexpected_error(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test user flow with unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_hass_splunk.check.side_effect = Exception("Unexpected error")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: "test-token-123",
            CONF_HOST: "splunk.example.com",
            CONF_PORT: 8088,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow when entry is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: "test-token-123",
            CONF_HOST: DEFAULT_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_success(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test successful import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_TOKEN: "test-token-123",
            CONF_HOST: "splunk.example.com",
            CONF_PORT: 8088,
            CONF_SSL: False,
            CONF_NAME: "Imported Splunk",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Imported Splunk"
    assert result["data"] == {
        CONF_TOKEN: "test-token-123",
        CONF_HOST: "splunk.example.com",
        CONF_PORT: 8088,
        CONF_SSL: False,
        CONF_NAME: "Imported Splunk",
    }


async def test_import_flow_invalid_config(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test import flow with invalid configuration."""
    mock_hass_splunk.check.side_effect = [False, True]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_TOKEN: "test-token-123",
            CONF_HOST: "invalid-host",
            CONF_PORT: 8088,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_config"


async def test_import_flow_already_configured(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test import flow when entry is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_TOKEN: "test-token-123",
            CONF_HOST: DEFAULT_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_success(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
            "unique_id": mock_config_entry.unique_id,
        },
        data=mock_config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "new-token-456"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_TOKEN] == "new-token-456"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth flow with invalid token."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
            "unique_id": mock_config_entry.unique_id,
        },
        data=mock_config_entry.data,
    )

    # Mock token check failure
    mock_hass_splunk.check.side_effect = [True, False]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "invalid-token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}
