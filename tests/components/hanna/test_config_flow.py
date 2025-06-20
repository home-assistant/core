"""Tests for the Hanna Instruments integration config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from hanna_cloud.client import AuthenticationError
import pytest

from homeassistant.components.hanna.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def mock_hanna_client():
    """Mock Hanna Cloud client."""
    with patch(
        "homeassistant.components.hanna.config_flow.HannaCloudClient"
    ) as mock_client:
        client = mock_client.return_value
        client.authenticate = (
            MagicMock()
        )  # Use MagicMock instead of AsyncMock since it's called synchronously
        yield client


async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hanna_client: MagicMock,
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
            "email": "test@example.com",
            "password": "test-password",
            "code": "test-code",
            "scan_interval": 1,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == {
        "email": "test@example.com",
        "password": "test-password",
        "code": "test-code",
        "scan_interval": 1,
    }


async def test_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hanna_client: MagicMock,
) -> None:
    """Test invalid authentication."""
    mock_hanna_client.authenticate.side_effect = AuthenticationError(
        "Invalid authentication"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": "test@example.com",
            "password": "test-password",
            "code": "test-code",
            "scan_interval": 1,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}
