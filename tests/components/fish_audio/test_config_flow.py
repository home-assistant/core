"""Config flow tests for Fish Audio."""

from unittest.mock import AsyncMock, MagicMock

from fishaudio import AuthenticationError, FishAudioError
from fishaudio.types.account import Credits
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.fish_audio.const import (
    CONF_BACKEND,
    CONF_LATENCY,
    CONF_SELF_ONLY,
    CONF_SORT_BY,
    CONF_SPEED,
    CONF_TITLE,
    CONF_USER_ID,
    CONF_VOICE_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LANGUAGE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_happy_path(
    hass: HomeAssistant, mock_fishaudio_client: AsyncMock
) -> None:
    """Test the full user flow happy path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "test-key"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fish Audio"
    assert result["data"] == {CONF_API_KEY: "test-key", CONF_USER_ID: "test_user"}
    assert result["result"].unique_id == "test_user"


@pytest.mark.parametrize(
    ("side_effect", "error_base"),
    [
        (FishAudioError("Connection error"), "cannot_connect"),
        (AuthenticationError(401, "Invalid API key"), "invalid_auth"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_user_flow_api_error(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error_base: str,
) -> None:
    """Test user flow with API errors during validation and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Simulate the error
    mock_fishaudio_client.account.get_credits.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "bad-key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error_base}

    mock_setup_entry.assert_not_called()

    # Clear the error and retry successfully
    mock_fishaudio_client.account.get_credits.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "test-key"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fish Audio"
    assert result["data"] == {CONF_API_KEY: "test-key", CONF_USER_ID: "test_user"}
    assert result["result"].unique_id == "test_user"

    mock_setup_entry.assert_called_once()


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fishaudio_client: AsyncMock,
) -> None:
    """Test that the user flow is aborted if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "test-api-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_fishaudio_client")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new-api-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"


@pytest.mark.parametrize(
    ("side_effect", "error_base"),
    [
        pytest.param(
            FishAudioError("Connection error"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(
            AuthenticationError(401, "Invalid API key"),
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(Exception("Unexpected error"), "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fishaudio_client: AsyncMock,
    side_effect: Exception,
    error_base: str,
) -> None:
    """Test reauthentication flow errors and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_fishaudio_client.account.get_credits.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "bad-key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error_base}

    mock_fishaudio_client.account.get_credits.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new-api-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_wrong_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fishaudio_client: AsyncMock,
) -> None:
    """Test reauthentication with an API key from a different account."""
    mock_config_entry.add_to_hass(hass)
    mock_fishaudio_client.account.get_credits.return_value = MagicMock(
        spec=Credits, user_id="other_user"
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "other-api-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_API_KEY] == "test-api-key"


async def test_subflow_happy_path(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the full subflow happy path."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "tts"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_TITLE: "",
            CONF_LANGUAGE: "en",
            CONF_SORT_BY: "task_count",
            CONF_SELF_ONLY: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_VOICE_ID: "voice-alpha",
            CONF_BACKEND: "s1",
            CONF_LATENCY: "balanced",
            CONF_SPEED: 1.5,
            CONF_NAME: "My Custom Voice",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Custom Voice"
    assert result["data"][CONF_VOICE_ID] == "voice-alpha"
    assert result["data"][CONF_BACKEND] == "s1"
    assert result["data"][CONF_LATENCY] == "balanced"
    assert result["data"][CONF_SPEED] == 1.5
    assert result["unique_id"] == "voice-alpha-s1"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert len(entry.subentries) == 3  # Two originals + new one


async def test_subflow_cannot_connect(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the subflow when fetching models fails."""
    mock_fishaudio_client.voices.list.side_effect = FishAudioError("API Error")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "tts"),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_LANGUAGE: "en"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_subflow_no_models_found(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the subflow when no voices are found."""
    mock_fishaudio_client.voices.list.return_value = AsyncMock(items=[])

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "tts"),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_LANGUAGE: "en"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_models_found"


async def test_subflow_reconfigure(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring an existing TTS subentry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    subentry = list(mock_config_entry.subentries.values())[0]

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "tts"),
        context={"source": "reconfigure", "subentry_id": subentry.subentry_id},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Step through reconfigure
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_TITLE: "",
            CONF_LANGUAGE: "es",
            CONF_SORT_BY: "task_count",
            CONF_SELF_ONLY: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_VOICE_ID: "voice-gamma",
            CONF_BACKEND: "s1",
            CONF_LATENCY: "normal",
            CONF_SPEED: 1.3,
            CONF_NAME: "Updated Voice",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.subentries[subentry.subentry_id].data[CONF_SPEED] == 1.3


async def test_subflow_reconfigure_already_configured(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring a TTS subentry to match an existing one."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Try to reconfigure the first subentry to match the second
    # one (which already exists)
    first_subentry = [
        s for s in mock_config_entry.subentries.values() if s.title == "Test Voice"
    ][0]

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "tts"),
        context={"source": "reconfigure", "subentry_id": first_subentry.subentry_id},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Step through reconfigure
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_TITLE: "",
            CONF_LANGUAGE: "en",
            CONF_SORT_BY: "task_count",
            CONF_SELF_ONLY: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    # Try to set the same voice_id and backend as the second subentry
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_VOICE_ID: "voice-beta",
            CONF_BACKEND: "s1",
            CONF_LATENCY: "normal",
            CONF_NAME: "Test Voice Updated",
        },
    )

    # Should abort because this combination already exists
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_subflow_entry_not_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test creating a TTS subentry when the parent entry is not loaded."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "tts"),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"
