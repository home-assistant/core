"""Tests for the Sequence config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from GetSequenceIoApiClient import (
    SequenceApiError,
    SequenceAuthError,
    SequenceConnectionError,
)
import pytest

from homeassistant.components.getsequence.config_flow import validate_input
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CONF_DATA_USER
from .const import DOMAIN

from tests.common import MockConfigEntry


class TestSequenceConfigFlow:
    """Test Sequence config flow."""

    async def test_user_flow_success(self, hass: HomeAssistant) -> None:
        """Test successful user flow."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        with patch(
            "homeassistant.components.getsequence.config_flow.validate_input",
            return_value={"title": "Sequence Account"},
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=CONF_DATA_USER,
            )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Sequence Account"
        assert result["data"] == CONF_DATA_USER

    async def test_user_flow_invalid_auth(self, hass: HomeAssistant) -> None:
        """Test user flow with invalid authentication."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        with patch(
            "homeassistant.components.getsequence.config_flow.validate_input",
            side_effect=SequenceAuthError("Invalid token"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=CONF_DATA_USER,
            )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_user_flow_cannot_connect(self, hass: HomeAssistant) -> None:
        """Test user flow with connection error."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        with patch(
            "homeassistant.components.getsequence.config_flow.validate_input",
            side_effect=SequenceConnectionError("Network error"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=CONF_DATA_USER,
            )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_user_flow_api_error(self, hass: HomeAssistant) -> None:
        """Test user flow with API error."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        with patch(
            "homeassistant.components.getsequence.config_flow.validate_input",
            side_effect=SequenceApiError("API error"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=CONF_DATA_USER,
            )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}

    async def test_user_flow_unexpected_exception(self, hass: HomeAssistant) -> None:
        """Test user flow with unexpected exception."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        with patch(
            "homeassistant.components.getsequence.config_flow.validate_input",
            side_effect=ValueError("Unexpected error"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=CONF_DATA_USER,
            )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}

    async def test_user_flow_duplicate_name(self, hass: HomeAssistant) -> None:
        """Test user flow prevents duplicate names."""
        entry = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        with patch(
            "homeassistant.components.getsequence.config_flow.validate_input",
            return_value={"title": "Sequence Account"},
        ):
            await hass.config_entries.flow.async_configure(
                entry["flow_id"],
                user_input=CONF_DATA_USER,
            )

        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        with patch(
            "homeassistant.components.getsequence.config_flow.validate_input",
            return_value={"title": "Sequence Account"},
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=CONF_DATA_USER,
            )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    async def test_reauth_flow_success(self, hass: HomeAssistant) -> None:
        """Test successful reauth flow."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=CONF_DATA_USER,
            title="Sequence Account",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        new_token = "test_token_reauth_new"
        with patch(
            "homeassistant.components.getsequence.config_flow.validate_input",
            return_value={"title": "Sequence Account"},
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_ACCESS_TOKEN: new_token},
            )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.data[CONF_ACCESS_TOKEN] == new_token

    async def test_reauth_flow_invalid_auth(self, hass: HomeAssistant) -> None:
        """Test reauth flow with invalid authentication."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=CONF_DATA_USER,
            title="Sequence Account",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )

        with patch(
            "homeassistant.components.getsequence.config_flow.validate_input",
            side_effect=SequenceAuthError("Invalid token"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_ACCESS_TOKEN: "bad_token"},
            )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_reauth_flow_cannot_connect(self, hass: HomeAssistant) -> None:
        """Test reauth flow with connection error."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=CONF_DATA_USER,
            title="Sequence Account",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )

        with patch(
            "homeassistant.components.getsequence.config_flow.validate_input",
            side_effect=SequenceConnectionError("Network error"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_ACCESS_TOKEN: "test_token"},
            )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_reauth_flow_api_error(self, hass: HomeAssistant) -> None:
        """Test reauth flow with API error."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=CONF_DATA_USER,
            title="Sequence Account",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )

        with patch(
            "homeassistant.components.getsequence.config_flow.validate_input",
            side_effect=SequenceApiError("API error"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_ACCESS_TOKEN: "test_token"},
            )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "unknown"}

    async def test_reauth_flow_unexpected_exception(self, hass: HomeAssistant) -> None:
        """Test reauth flow with unexpected exception."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=CONF_DATA_USER,
            title="Sequence Account",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )

        with patch(
            "homeassistant.components.getsequence.config_flow.validate_input",
            side_effect=RuntimeError("Unexpected error"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_ACCESS_TOKEN: "test_token"},
            )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "unknown"}


class TestValidateInput:
    """Test the validate_input helper function."""

    async def test_validate_input_success(self, hass: HomeAssistant) -> None:
        """Test successful validation."""
        mock_client = AsyncMock()
        mock_client.async_get_accounts = AsyncMock(
            return_value={"data": {"accounts": []}}
        )

        with patch(
            "homeassistant.components.getsequence.config_flow.SequenceApiClient",
            return_value=mock_client,
        ):
            result = await validate_input(hass, CONF_DATA_USER)

        assert result == {"title": "Sequence Account"}
        mock_client.async_get_accounts.assert_called_once()

    async def test_validate_input_auth_error(self, hass: HomeAssistant) -> None:
        """Test validate_input with auth error."""
        mock_client = AsyncMock()
        mock_client.async_get_accounts = AsyncMock(
            side_effect=SequenceAuthError("Invalid token")
        )

        with (
            patch(
                "homeassistant.components.getsequence.config_flow.SequenceApiClient",
                return_value=mock_client,
            ),
            pytest.raises(SequenceAuthError),
        ):
            await validate_input(hass, CONF_DATA_USER)

    async def test_validate_input_connection_error(self, hass: HomeAssistant) -> None:
        """Test validate_input with connection error."""
        mock_client = AsyncMock()
        mock_client.async_get_accounts = AsyncMock(
            side_effect=SequenceConnectionError("Network error")
        )

        with (
            patch(
                "homeassistant.components.getsequence.config_flow.SequenceApiClient",
                return_value=mock_client,
            ),
            pytest.raises(SequenceConnectionError),
        ):
            await validate_input(hass, CONF_DATA_USER)

    async def test_validate_input_api_error(self, hass: HomeAssistant) -> None:
        """Test validate_input with API error."""
        mock_client = AsyncMock()
        mock_client.async_get_accounts = AsyncMock(
            side_effect=SequenceApiError("API error")
        )

        with (
            patch(
                "homeassistant.components.getsequence.config_flow.SequenceApiClient",
                return_value=mock_client,
            ),
            pytest.raises(SequenceApiError),
        ):
            await validate_input(hass, CONF_DATA_USER)
