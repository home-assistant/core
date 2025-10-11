"""Tests for the Alexa Devices config flow."""

from unittest.mock import AsyncMock

from aioamazondevices.exceptions import (
    CannotAuthenticate,
    CannotConnect,
    CannotRetrieveData,
)
import pytest

from homeassistant.components.alexa_devices.const import (
    CONF_LOGIN_DATA,
    CONF_SITE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_CODE, TEST_PASSWORD, TEST_USERNAME

from tests.common import MockConfigEntry


async def test_flow_with_missing_customer_info(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test flow when customer_info is missing from API response."""
    # Mock API response without customer_info (simulating the bug)
    mock_amazon_devices_client.login_mode_interactive.return_value = {
        CONF_SITE: "https://www.amazon.com",
        # customer_info is intentionally missing
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_CODE: TEST_CODE,
        },
    )

    # Should succeed with fallback customer_info
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USERNAME
    assert "customer_info" in result["data"][CONF_LOGIN_DATA]
    assert result["data"][CONF_LOGIN_DATA]["customer_info"]["user_id"] is not None
    # Unique ID should be set to the fallback value
    assert result["result"].unique_id is not None


async def test_flow_with_incomplete_customer_info(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test flow when customer_info exists but user_id is missing."""
    # Mock API response with incomplete customer_info
    mock_amazon_devices_client.login_mode_interactive.return_value = {
        CONF_SITE: "https://www.amazon.com",
        "customer_info": {
            # user_id is missing
            "name": "Test User",
        },
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_CODE: TEST_CODE,
        },
    )

    # Should succeed with fallback user_id
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USERNAME
    assert "customer_info" in result["data"][CONF_LOGIN_DATA]
    assert result["data"][CONF_LOGIN_DATA]["customer_info"]["user_id"] is not None
    # Unique ID should be set to the fallback value
    assert result["result"].unique_id is not None


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
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_CODE: TEST_CODE,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USERNAME
    assert result["data"] == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_LOGIN_DATA: {
            "customer_info": {"user_id": TEST_USERNAME},
            CONF_SITE: "https://www.amazon.com",
        },
    }
    assert result["result"].unique_id == TEST_USERNAME
    mock_amazon_devices_client.login_mode_interactive.assert_called_once_with("023123")


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (CannotConnect, "cannot_connect"),
        (CannotAuthenticate, "invalid_auth"),
        (CannotRetrieveData, "cannot_retrieve_data"),
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
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_CODE: TEST_CODE,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_amazon_devices_client.login_mode_interactive.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_CODE: TEST_CODE,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
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
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_CODE: TEST_CODE,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_successful(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test starting a reauthentication flow."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSWORD: "other_fake_password",
            CONF_CODE: "000000",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry.data == {
        CONF_CODE: "000000",
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: "other_fake_password",
        CONF_LOGIN_DATA: {
            "customer_info": {"user_id": TEST_USERNAME},
            CONF_SITE: "https://www.amazon.com",
        },
    }


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (CannotConnect, "cannot_connect"),
        (CannotAuthenticate, "invalid_auth"),
        (CannotRetrieveData, "cannot_retrieve_data"),
    ],
)
async def test_reauth_not_successful(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    error: str,
) -> None:
    """Test starting a reauthentication flow but no connection found."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_amazon_devices_client.login_mode_interactive.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSWORD: "other_fake_password",
            CONF_CODE: "000000",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_amazon_devices_client.login_mode_interactive.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSWORD: "fake_password",
            CONF_CODE: "111111",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_CODE: "111111",
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: "fake_password",
        CONF_LOGIN_DATA: {
            "customer_info": {"user_id": TEST_USERNAME},
            CONF_SITE: "https://www.amazon.com",
        },
    }


async def test_reconfigure_successful(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the entry can be reconfigured."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # original entry
    assert mock_config_entry.data[CONF_USERNAME] == TEST_USERNAME

    new_password = "new_fake_password"

    reconfigure_result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSWORD: new_password,
            CONF_CODE: TEST_CODE,
        },
    )

    assert reconfigure_result["type"] is FlowResultType.ABORT
    assert reconfigure_result["reason"] == "reconfigure_successful"

    # changed entry
    assert mock_config_entry.data == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: new_password,
        CONF_LOGIN_DATA: {
            "customer_info": {"user_id": TEST_USERNAME},
            CONF_SITE: "https://www.amazon.com",
        },
    }


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (CannotConnect, "cannot_connect"),
        (CannotAuthenticate, "invalid_auth"),
        (CannotRetrieveData, "cannot_retrieve_data"),
    ],
)
async def test_reconfigure_fails(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    error: str,
) -> None:
    """Test that the host can be reconfigured."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_amazon_devices_client.login_mode_interactive.side_effect = side_effect

    reconfigure_result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_CODE: TEST_CODE,
        },
    )

    assert reconfigure_result["type"] is FlowResultType.FORM
    assert reconfigure_result["step_id"] == "reconfigure"
    assert reconfigure_result["errors"] == {"base": error}

    mock_amazon_devices_client.login_mode_interactive.side_effect = None

    reconfigure_result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_CODE: TEST_CODE,
        },
    )

    assert reconfigure_result["type"] is FlowResultType.ABORT
    assert reconfigure_result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_LOGIN_DATA: {
            "customer_info": {"user_id": TEST_USERNAME},
            CONF_SITE: "https://www.amazon.com",
        },
    }
