"""Config flow tests for Fish Audio."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fish_audio_sdk.schemas import APICreditEntity
import pytest

from homeassistant.components.fish_audio.const import (
    CONF_API_KEY,
    CONF_BACKEND,
    CONF_LANGUAGE,
    CONF_NAME,
    CONF_SELF_ONLY,
    CONF_SORT_BY,
    CONF_USER_ID,
    CONF_VOICE_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _prime_models(mock_async_client: MagicMock) -> None:
    """Give the session a predictable models payload for the happy path."""
    sess = mock_async_client.return_value
    sess.list_models.return_value = SimpleNamespace(
        items=[
            SimpleNamespace(id="z-id", title="Zulu"),
            SimpleNamespace(id="a-id", title="Alpha"),
            SimpleNamespace(id="m-id", title="Mike"),
        ]
    )


class TestConfigFlow:
    """Test the main user configuration flow."""

    async def test_user_flow_happy_path(
        self, hass: HomeAssistant, mock_async_client: MagicMock
    ) -> None:
        """Test the full user flow happy path."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        with patch(
            "homeassistant.components.fish_audio.async_setup_entry", return_value=True
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_API_KEY: "key123"}
            )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Fish Audio"
        assert result["data"] == {
            CONF_API_KEY: "key123",
            CONF_USER_ID: "test_user",
        }

    @pytest.mark.parametrize(
        ("fixture", "error_base"),
        [
            ("mock_async_client_connect_error", "cannot_connect"),
            ("mock_async_client_auth_error", "invalid_auth"),
            ("mock_async_client_generic_error", "unknown"),
        ],
    )
    async def test_user_flow_api_error(
        self,
        hass: HomeAssistant,
        request: pytest.FixtureRequest,
        fixture: str,
        error_base: str,
    ) -> None:
        """Test user flow with API errors during validation."""
        request.getfixturevalue(fixture)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "any-key"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": error_base}

    async def test_user_flow_already_configured(
        self,
        hass: HomeAssistant,
        mock_entry: MockConfigEntry,
        mock_async_client: MagicMock,
    ) -> None:
        """Test that the user flow is aborted if already configured."""
        mock_entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "key123"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


class TestReauthFlow:
    """Test the re-authentication flow."""

    async def test_reauth_flow_happy_path(
        self,
        hass: HomeAssistant,
        mock_entry: MockConfigEntry,
        mock_async_client: MagicMock,
    ) -> None:
        """Test the full re-authentication flow."""
        mock_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.fish_audio.config_flow.FishAudioConfigFlowManager.validate_api_key",
            return_value=APICreditEntity(
                _id="test_id",
                user_id=mock_entry.unique_id,
                credit=Decimal("100.0"),
                created_at="2023-01-01T00:00:00Z",
                updated_at="2023-01-01T00:00:00Z",
            ),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={
                    "source": SOURCE_REAUTH,
                    "entry_id": mock_entry.entry_id,
                },
                data=mock_entry.data,
            )
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "reauth_confirm"

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_API_KEY: "new-key"}
            )
            await hass.async_block_till_done()

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"

    async def test_reauth_flow_invalid_key(
        self,
        hass: HomeAssistant,
        mock_entry: MockConfigEntry,
        mock_async_client_auth_error: MagicMock,
    ) -> None:
        """Test re-authentication with an invalid key."""
        mock_entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "entry_id": mock_entry.entry_id,
            },
            data=mock_entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "bad-key"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "invalid_auth"}


class TestSubentryFlow:
    """Test the TTS sub-entry flow."""

    async def test_subflow_happy_path(
        self,
        hass: HomeAssistant,
        mock_async_client: MagicMock,
        mock_entry: MockConfigEntry,
    ) -> None:
        """Test the full subflow happy path."""
        _prime_models(mock_async_client)
        mock_entry.add_to_hass(hass)

        # In tests, we initiate the sub-flow via the subentries manager.
        result = await hass.config_entries.subentries.async_init(
            (mock_entry.entry_id, "tts"),
            context={"source": SOURCE_USER},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                CONF_SELF_ONLY: True,
                CONF_LANGUAGE: "en",
                CONF_SORT_BY: "score",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "model"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_VOICE_ID: "a-id", CONF_BACKEND: "s1"},
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "name"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_NAME: "My Custom Voice"},
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "My Custom Voice"
        assert result["data"] == {
            CONF_SELF_ONLY: True,
            CONF_LANGUAGE: "en",
            CONF_SORT_BY: "score",
            CONF_VOICE_ID: "a-id",
            CONF_BACKEND: "s1",
            CONF_NAME: "My Custom Voice",
        }

    async def test_subflow_no_models_found(
        self,
        hass: HomeAssistant,
        mock_async_client: MagicMock,
        mock_entry: MockConfigEntry,
    ) -> None:
        """Test the subflow when fetching models fails."""
        mock_async_client.return_value.list_models.side_effect = Exception("API Error")
        mock_entry.add_to_hass(hass)

        result = await hass.config_entries.subentries.async_init(
            (mock_entry.entry_id, "tts"),
            context={"source": SOURCE_USER},
        )

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_LANGUAGE: "en"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "model"
        assert result["errors"] == {"base": "no_models_found"}

    async def test_subflow_no_model_selected(
        self,
        hass: HomeAssistant,
        mock_async_client: MagicMock,
        mock_entry: MockConfigEntry,
    ) -> None:
        """Test the subflow when no model is selected."""
        _prime_models(mock_async_client)
        mock_entry.add_to_hass(hass)

        result = await hass.config_entries.subentries.async_init(
            (mock_entry.entry_id, "tts"),
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={}
        )

        # Submit the model form with no voice selected
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_BACKEND: "s1"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "model"
        assert result["errors"] == {"base": "no_model_selected"}
