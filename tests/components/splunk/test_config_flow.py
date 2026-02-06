"""Test the Splunk config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.splunk.const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_flow_success(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "splunk.example.com:8088"
    assert result["data"] == {
        CONF_TOKEN: "test-token-123",
        CONF_HOST: "splunk.example.com",
        CONF_PORT: 8088,
        CONF_SSL: True,
        CONF_VERIFY_SSL: True,
        CONF_NAME: "Test Splunk",
    }

    # Verify that check was called twice (connectivity and token)
    assert mock_hass_splunk.check.call_count == 2


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        ([False, True], "cannot_connect"),
        ([True, False], "invalid_auth"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_user_flow_error_and_recovery(
    hass: HomeAssistant,
    mock_hass_splunk: AsyncMock,
    side_effect: list[bool] | Exception,
    error: str,
) -> None:
    """Test user flow errors and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_hass_splunk.check.side_effect = side_effect

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
    assert result["errors"] == {"base": error}

    # Test recovery by resetting mock and completing successfully
    mock_hass_splunk.check.side_effect = None
    mock_hass_splunk.check.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: "test-token-123",
            CONF_HOST: "splunk.example.com",
            CONF_PORT: 8088,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow when entry is already configured (single instance)."""
    mock_config_entry.add_to_hass(hass)

    # With single_config_entry in manifest, flow should abort immediately
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_import_flow_success(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test successful import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_TOKEN: "test-token-123",
            CONF_HOST: "splunk.example.com",
            CONF_PORT: 8088,
            CONF_SSL: False,
            CONF_NAME: "Imported Splunk",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "splunk.example.com:8088"
    assert result["data"] == {
        CONF_TOKEN: "test-token-123",
        CONF_HOST: "splunk.example.com",
        CONF_PORT: 8088,
        CONF_SSL: False,
        CONF_NAME: "Imported Splunk",
    }


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        ([False, True], "cannot_connect"),
        ([True, False], "invalid_auth"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_import_flow_error_and_recovery(
    hass: HomeAssistant,
    mock_hass_splunk: AsyncMock,
    side_effect: list[bool] | Exception,
    reason: str,
) -> None:
    """Test import flow errors and recovery."""
    mock_hass_splunk.check.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_TOKEN: "test-token-123",
            CONF_HOST: "splunk.example.com",
            CONF_PORT: 8088,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason

    # Test recovery by resetting mock and importing again
    mock_hass_splunk.check.side_effect = None
    mock_hass_splunk.check.return_value = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_TOKEN: "test-token-123",
            CONF_HOST: "splunk.example.com",
            CONF_PORT: 8088,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_import_flow_already_configured(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test import flow when entry is already configured (single instance)."""
    mock_config_entry.add_to_hass(hass)

    # With single_config_entry in manifest, import should abort immediately
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_TOKEN: "test-token-123",
            CONF_HOST: DEFAULT_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reauth_flow_success(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "new-token-456"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_TOKEN] == "new-token-456"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth flow with invalid token and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    # Mock token check failure
    mock_hass_splunk.check.side_effect = [True, False]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "invalid-token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    # Now test that we can recover from the error
    mock_hass_splunk.check.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "new-valid-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_TOKEN] == "new-valid-token"
