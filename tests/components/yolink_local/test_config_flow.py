"""Tests for the YoLink Local config flow."""

from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.yolink_local.config_flow import (
    CannotConnect,
    InvalidAuth,
    validate_input,
)
from homeassistant.components.yolink_local.const import CONF_NET_ID, DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

# Test data
TEST_HOST = "192.168.1.100"
TEST_NET_ID = "test_net_id_123"
TEST_CLIENT_ID = "test_client_id"
TEST_CLIENT_SECRET = "test_client_secret"

TEST_USER_INPUT = {
    CONF_HOST: TEST_HOST,
    CONF_NET_ID: TEST_NET_ID,
    CONF_CLIENT_ID: TEST_CLIENT_ID,
    CONF_CLIENT_SECRET: TEST_CLIENT_SECRET,
}


@pytest.fixture
def mock_yolink_client_success():
    """Mock successful YoLinkLocalHubClient."""
    with patch(
        "homeassistant.components.yolink_local.config_flow.YoLinkLocalHubClient"
    ) as mock_client:
        client_instance = Mock()
        client_instance.authenticate = AsyncMock(return_value=True)
        mock_client.return_value = client_instance
        yield mock_client


async def test_form_display(hass: HomeAssistant) -> None:
    """Test that the form is displayed correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry, mock_yolink_client_success
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "YoLink Local Hub"
    assert result["data"] == TEST_USER_INPUT
    assert result["result"].unique_id == f"yolink_local_{TEST_NET_ID}"


async def test_user_flow_cannot_connect(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test connection error handling."""
    with patch(
        "homeassistant.components.yolink_local.config_flow.YoLinkLocalHubClient"
    ) as mock_client:
        client_instance = Mock()
        client_instance.authenticate = AsyncMock(side_effect=ClientError())
        mock_client.return_value = client_instance

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
        assert result["step_id"] == "user"


async def test_user_flow_invalid_auth(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test invalid authentication handling."""
    with patch(
        "homeassistant.components.yolink_local.config_flow.YoLinkLocalHubClient"
    ) as mock_client:
        client_instance = Mock()
        client_instance.authenticate = AsyncMock(return_value=False)
        mock_client.return_value = client_instance

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}
        assert result["step_id"] == "user"


async def test_user_flow_unexpected_exception(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test unexpected exception handling."""
    with patch(
        "homeassistant.components.yolink_local.config_flow.YoLinkLocalHubClient"
    ) as mock_client:
        client_instance = Mock()
        client_instance.authenticate = AsyncMock(
            side_effect=Exception("Unexpected error")
        )
        mock_client.return_value = client_instance

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}
        assert result["step_id"] == "user"


async def test_user_flow_duplicate_entry(
    hass: HomeAssistant, mock_setup_entry, mock_yolink_client_success
) -> None:
    """Test duplicate config entry detection."""
    # Create an existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"yolink_local_{TEST_NET_ID}",
        data=TEST_USER_INPUT,
    )
    entry.add_to_hass(hass)

    # Start a new flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    # Try to configure with the same NET_ID
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    # Should abort due to duplicate
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_validate_input_success(hass: HomeAssistant) -> None:
    """Test validate_input with successful authentication."""
    with patch(
        "homeassistant.components.yolink_local.config_flow.YoLinkLocalHubClient"
    ) as mock_client:
        client_instance = Mock()
        client_instance.authenticate = AsyncMock(return_value=True)
        mock_client.return_value = client_instance

        result = await validate_input(hass, TEST_USER_INPUT)

        assert result == {"title": "YoLink Local Hub"}
        mock_client.assert_called_once()
        mock_client.return_value.authenticate.assert_called_once()


async def test_validate_input_client_error(hass: HomeAssistant) -> None:
    """Test validate_input with ClientError."""

    with patch(
        "homeassistant.components.yolink_local.config_flow.YoLinkLocalHubClient"
    ) as mock_client:
        client_instance = Mock()
        client_instance.authenticate = AsyncMock(side_effect=ClientError())
        mock_client.return_value = client_instance

        with pytest.raises(CannotConnect):
            await validate_input(hass, TEST_USER_INPUT)


async def test_validate_input_invalid_auth(hass: HomeAssistant) -> None:
    """Test validate_input with invalid authentication."""

    with patch(
        "homeassistant.components.yolink_local.config_flow.YoLinkLocalHubClient"
    ) as mock_client:
        client_instance = Mock()
        client_instance.authenticate = AsyncMock(return_value=False)
        mock_client.return_value = client_instance

        with pytest.raises(InvalidAuth):
            await validate_input(hass, TEST_USER_INPUT)


async def test_user_flow_retry_after_error(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test that user can retry after an error."""
    with patch(
        "homeassistant.components.yolink_local.config_flow.YoLinkLocalHubClient"
    ) as mock_client:
        client_instance = Mock()
        # First attempt fails
        client_instance.authenticate = AsyncMock(return_value=False)
        mock_client.return_value = client_instance

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

        # Second attempt succeeds
        client_instance.authenticate = AsyncMock(return_value=True)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "YoLink Local Hub"
