"""Test the ElevenLabs text-to-speech config flow."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.elevenlabs.const import (
    CONF_CONFIGURE_VOICE,
    CONF_SIMILARITY,
    CONF_STABILITY,
    CONF_STT_AUTO_LANGUAGE,
    CONF_STT_MODEL,
    CONF_STYLE,
    CONF_USE_SPEAKER_BOOST,
    CONF_VOICE,
    DEFAULT_SIMILARITY,
    DEFAULT_STABILITY,
    DEFAULT_STT_MODEL,
    DEFAULT_STYLE,
    DEFAULT_TTS_MODEL,
    DEFAULT_USE_SPEAKER_BOOST,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_step(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_async_client: AsyncMock,
) -> None:
    """Test user step create entry result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "api_key",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ElevenLabs"
    assert result["data"] == {
        "api_key": "api_key",
    }
    assert result["options"] == {
        CONF_MODEL: DEFAULT_TTS_MODEL,
        CONF_VOICE: "voice1",
        CONF_STT_MODEL: DEFAULT_STT_MODEL,
        CONF_STT_AUTO_LANGUAGE: False,
    }

    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("client_fixture", "error"),
    [
        pytest.param(
            "mock_async_client_api_error", "invalid_api_key", id="invalid_api_key"
        ),
        pytest.param(
            "mock_async_client_api_key_id_error",
            "api_key_id_used",
            id="api_key_id_used",
        ),
        pytest.param(
            "mock_async_client_invalid_key_code_error",
            "invalid_api_key",
            id="invalid_api_key_code",
        ),
        pytest.param(
            "mock_async_client_connect_error", "cannot_connect", id="cannot_connect"
        ),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    request: pytest.FixtureRequest,
    client_fixture: str,
    error: str,
) -> None:
    """Test user step errors and recovery."""
    request.getfixturevalue(client_fixture)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "api_key",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_setup_entry.assert_not_called()

    # Use a working client
    request.getfixturevalue("mock_async_client")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "api_key",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ElevenLabs"
    assert result["data"] == {
        "api_key": "api_key",
    }
    assert result["options"] == {
        CONF_MODEL: DEFAULT_TTS_MODEL,
        CONF_VOICE: "voice1",
        CONF_STT_MODEL: DEFAULT_STT_MODEL,
        CONF_STT_AUTO_LANGUAGE: False,
    }

    mock_setup_entry.assert_called_once()


async def test_voices_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_async_client_voices_error: AsyncMock,
    request: pytest.FixtureRequest,
) -> None:
    """Test user step with invalid api key."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "api_key",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_setup_entry.assert_not_called()

    # Use a working client
    request.getfixturevalue("mock_async_client")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "api_key",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ElevenLabs"
    assert result["data"] == {
        "api_key": "api_key",
    }
    assert result["options"] == {
        CONF_MODEL: DEFAULT_TTS_MODEL,
        CONF_VOICE: "voice1",
        CONF_STT_MODEL: DEFAULT_STT_MODEL,
        CONF_STT_AUTO_LANGUAGE: False,
    }

    mock_setup_entry.assert_called_once()


async def test_models_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_async_client_models_error: AsyncMock,
    request: pytest.FixtureRequest,
) -> None:
    """Test user step with invalid api key."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "api_key",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_setup_entry.assert_not_called()

    # Use a working client
    request.getfixturevalue("mock_async_client")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "api_key",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ElevenLabs"
    assert result["data"] == {
        "api_key": "api_key",
    }
    assert result["options"] == {
        CONF_MODEL: DEFAULT_TTS_MODEL,
        CONF_VOICE: "voice1",
        CONF_STT_MODEL: DEFAULT_STT_MODEL,
        CONF_STT_AUTO_LANGUAGE: False,
    }

    mock_setup_entry.assert_called_once()


async def test_options_flow_init(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_async_client: AsyncMock,
    mock_entry: MockConfigEntry,
) -> None:
    """Test options flow init."""
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODEL: "model1",
            CONF_VOICE: "voice1",
            CONF_STT_MODEL: "scribe_v1_experimental",
            CONF_STT_AUTO_LANGUAGE: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_entry.options == {
        CONF_MODEL: "model1",
        CONF_VOICE: "voice1",
        CONF_STT_MODEL: "scribe_v1_experimental",
        CONF_STT_AUTO_LANGUAGE: True,
    }

    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_voice_settings_default(
    hass: HomeAssistant, mock_async_client: AsyncMock, mock_entry: MockConfigEntry
) -> None:
    """Test options flow voice settings."""
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODEL: "model1",
            CONF_VOICE: "voice1",
            CONF_STT_MODEL: "scribe_v1_experimental",
            CONF_STT_AUTO_LANGUAGE: False,
            CONF_CONFIGURE_VOICE: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "voice_settings"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_entry.options == {
        CONF_MODEL: "model1",
        CONF_VOICE: "voice1",
        CONF_STT_MODEL: "scribe_v1_experimental",
        CONF_STT_AUTO_LANGUAGE: False,
        CONF_SIMILARITY: DEFAULT_SIMILARITY,
        CONF_STABILITY: DEFAULT_STABILITY,
        CONF_STYLE: DEFAULT_STYLE,
        CONF_USE_SPEAKER_BOOST: DEFAULT_USE_SPEAKER_BOOST,
    }


@pytest.mark.usefixtures("mock_setup_entry", "mock_async_client")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
) -> None:
    """Test reauthentication flow."""
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new_api_key"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data == {CONF_API_KEY: "new_api_key"}


@pytest.mark.parametrize(
    ("client_fixture", "error"),
    [
        pytest.param(
            "mock_async_client_api_error", "invalid_api_key", id="invalid_api_key"
        ),
        pytest.param(
            "mock_async_client_api_key_id_error",
            "api_key_id_used",
            id="api_key_id_used",
        ),
        pytest.param(
            "mock_async_client_invalid_key_code_error",
            "invalid_api_key",
            id="invalid_api_key_code",
        ),
        pytest.param("mock_async_client_voices_error", "unknown", id="unknown"),
        pytest.param(
            "mock_async_client_connect_error", "cannot_connect", id="cannot_connect"
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    request: pytest.FixtureRequest,
    client_fixture: str,
    error: str,
) -> None:
    """Test reauthentication flow errors and recovery."""
    mock_entry.add_to_hass(hass)
    request.getfixturevalue(client_fixture)

    result = await mock_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new_api_key"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    request.getfixturevalue("mock_async_client")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new_api_key"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data == {CONF_API_KEY: "new_api_key"}
