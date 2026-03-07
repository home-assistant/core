"""Tests for PulseGrow config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from aiopulsegrow import PulsegrowError
import pytest

from homeassistant.components.pulsegrow.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> MagicMock:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.pulsegrow.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
) -> None:
    """Test successful user flow."""
    with patch(
        "homeassistant.components.pulsegrow.config_flow.PulsegrowClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_user = MagicMock()
        mock_user.user_id = "test-account-id"
        mock_user.user_name = "Test User"
        mock_client.get_users = AsyncMock(return_value=[mock_user])

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "test-api-key"},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Test User"
        assert result["data"] == {CONF_API_KEY: "test-api-key"}
        assert result["result"].unique_id == "test-account-id"


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user flow with connection error."""
    with patch(
        "homeassistant.components.pulsegrow.config_flow.PulsegrowClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.get_users = AsyncMock(
            side_effect=PulsegrowError("Connection failed")
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "invalid-key"},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test user flow with unknown error."""
    with patch(
        "homeassistant.components.pulsegrow.config_flow.PulsegrowClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.get_users = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "test-key"},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test user flow when account is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Existing User",
        data={CONF_API_KEY: "existing-key"},
        unique_id="test-account-id",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.pulsegrow.config_flow.PulsegrowClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_user = MagicMock()
        mock_user.user_id = "test-account-id"
        mock_user.user_name = "Test User"
        mock_client.get_users = AsyncMock(return_value=[mock_user])

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "new-key"},
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
