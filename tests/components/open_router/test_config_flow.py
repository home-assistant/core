"""Test the OpenRouter config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from python_open_router import OpenRouterError

from homeassistant.components.open_router.const import (
    CONF_PROMPT,
    CONF_TTS_SPEED,
    CONF_TTS_VOICE,
    CONF_WEB_SEARCH,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import get_subentry_id, setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(
    hass: HomeAssistant, mock_open_router_client: AsyncMock
) -> None:
    """Test the full config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bla"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test account"
    assert result["data"] == {CONF_API_KEY: "bla"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_second_account(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a second account with a different API key can be added."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "different_key"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test account"
    assert result["data"] == {CONF_API_KEY: "different_key"}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (OpenRouterError("exception"), "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_errors(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle errors from the OpenRouter API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_open_router_client.get_key_data.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bla"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_open_router_client.get_key_data.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bla"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting the flow if an entry already exists."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bla"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_create_conversation_agent(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation agent."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "init"

    assert result["data_schema"].schema["model"].config["options"] == [
        {"value": "openai/gpt-3.5-turbo", "label": "OpenAI: GPT-3.5 Turbo"},
        {"value": "openai/gpt-4", "label": "OpenAI: GPT-4"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "openai/gpt-3.5-turbo",
            CONF_PROMPT: "you are an assistant",
            CONF_LLM_HASS_API: ["assist"],
            CONF_WEB_SEARCH: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_MODEL: "openai/gpt-3.5-turbo",
        CONF_PROMPT: "you are an assistant",
        CONF_LLM_HASS_API: ["assist"],
        CONF_WEB_SEARCH: False,
    }


async def test_create_conversation_agent_no_control(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation agent without control over the LLM API."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "init"

    assert result["data_schema"].schema["model"].config["options"] == [
        {"value": "openai/gpt-3.5-turbo", "label": "OpenAI: GPT-3.5 Turbo"},
        {"value": "openai/gpt-4", "label": "OpenAI: GPT-4"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "openai/gpt-3.5-turbo",
            CONF_PROMPT: "you are an assistant",
            CONF_LLM_HASS_API: [],
            CONF_WEB_SEARCH: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_MODEL: "openai/gpt-3.5-turbo",
        CONF_PROMPT: "you are an assistant",
        CONF_WEB_SEARCH: False,
    }


async def test_create_ai_task(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating an AI Task."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_data"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "init"

    assert result["data_schema"].schema["model"].config["options"] == [
        {"value": "openai/gpt-4", "label": "OpenAI: GPT-4"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "openai/gpt-4"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_MODEL: "openai/gpt-4"}


@pytest.mark.parametrize(
    "subentry_type",
    ["conversation", "ai_task_data"],
)
@pytest.mark.parametrize(
    ("exception", "reason"),
    [(OpenRouterError("exception"), "cannot_connect"), (Exception, "unknown")],
)
async def test_subentry_exceptions(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    subentry_type: str,
    exception: Exception,
    reason: str,
) -> None:
    """Test subentry flow exceptions."""
    await setup_integration(hass, mock_config_entry)

    mock_open_router_client.get_models.side_effect = exception

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, subentry_type),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("mock_openai_client")
async def test_create_tts_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_open_router_client: AsyncMock,
) -> None:
    """Test creating a TTS service, including the voice-selection step."""
    await setup_integration(hass, mock_config_entry)

    tts_model = MagicMock()
    tts_model.id = "openai/gpt-4o-mini-tts"
    tts_model.name = "GPT-4o mini TTS"
    tts_model.supported_voices = ["alloy", "echo"]
    tts_model_2 = MagicMock()
    tts_model_2.id = "some/other-tts"
    tts_model_2.name = "Other TTS"
    tts_model_2.supported_voices = None
    mock_open_router_client.get_models.return_value = [tts_model, tts_model_2]

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "tts"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"].schema["model"].config["options"] == [
        {"value": "openai/gpt-4o-mini-tts", "label": "GPT-4o mini TTS"},
        {"value": "some/other-tts", "label": "Other TTS"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "openai/gpt-4o-mini-tts"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "voice"
    assert result["data_schema"].schema["tts_voice"].config["options"] == [
        {"value": "alloy", "label": "alloy"},
        {"value": "echo", "label": "echo"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_TTS_VOICE: "echo", CONF_TTS_SPEED: 1.0},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "GPT-4o mini TTS"
    assert result["data"] == {
        CONF_MODEL: "openai/gpt-4o-mini-tts",
        "supported_voices": ["alloy", "echo"],
        CONF_TTS_VOICE: "echo",
        CONF_TTS_SPEED: 1.0,
    }


@pytest.mark.usefixtures("mock_openai_client")
async def test_create_stt_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_open_router_client: AsyncMock,
) -> None:
    """Test creating an STT service."""
    await setup_integration(hass, mock_config_entry)

    stt_model = MagicMock()
    stt_model.id = "openai/whisper-large-v3"
    stt_model.name = "Whisper Large v3"
    mock_open_router_client.get_models.return_value = [stt_model]

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "stt"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"].schema["model"].config["options"] == [
        {"value": "openai/whisper-large-v3", "label": "Whisper Large v3"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "openai/whisper-large-v3"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Whisper Large v3"
    assert result["data"] == {CONF_MODEL: "openai/whisper-large-v3"}


@pytest.mark.parametrize("subentry_type", ["tts", "stt"])
@pytest.mark.usefixtures("mock_openai_client")
async def test_model_subentry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_open_router_client: AsyncMock,
    subentry_type: str,
) -> None:
    """Test connection and HTTP errors abort the model flow with cannot_connect."""
    await setup_integration(hass, mock_config_entry)

    mock_open_router_client.get_models.side_effect = OpenRouterError("exception")

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, subentry_type),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize("subentry_type", ["tts", "stt"])
@pytest.mark.usefixtures("mock_openai_client")
async def test_model_subentry_unknown_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_open_router_client: AsyncMock,
    subentry_type: str,
) -> None:
    """Test an unexpected error aborts the model flow with unknown."""
    await setup_integration(hass, mock_config_entry)

    mock_open_router_client.get_models.side_effect = ValueError("boom")

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, subentry_type),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.parametrize("subentry_type", ["tts", "stt"])
@pytest.mark.usefixtures("mock_openai_client")
async def test_model_subentry_no_models(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_open_router_client: AsyncMock,
    subentry_type: str,
) -> None:
    """Test the model flow aborts when no models are available for the modality."""
    await setup_integration(hass, mock_config_entry)

    mock_open_router_client.get_models.return_value = []

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, subentry_type),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_models"


@pytest.mark.usefixtures("mock_openai_client")
async def test_create_tts_service_fallback_voices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_open_router_client: AsyncMock,
) -> None:
    """Test creating a TTS service for a model that exposes no voices."""
    await setup_integration(hass, mock_config_entry)

    tts_model = MagicMock()
    tts_model.id = "some/other-tts"
    tts_model.name = "Other TTS"
    tts_model.supported_voices = None
    mock_open_router_client.get_models.return_value = [tts_model]

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "tts"),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "some/other-tts"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "voice"
    voice_options = result["data_schema"].schema["tts_voice"].config["options"]
    assert {"value": "alloy", "label": "Alloy"} in voice_options
    assert {"value": "cedar", "label": "Cedar"} in voice_options
    voice_key = next(k for k in result["data_schema"].schema if k == CONF_TTS_VOICE)
    assert voice_key.default() == "alloy"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_TTS_VOICE: "shimmer", CONF_TTS_SPEED: 1.0},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_MODEL: "some/other-tts",
        "supported_voices": None,
        CONF_TTS_VOICE: "shimmer",
        CONF_TTS_SPEED: 1.0,
    }


@pytest.mark.usefixtures("mock_openai_client")
async def test_reconfigure_tts_service(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
) -> None:
    """Test reconfiguring a TTS service, including the voice step."""
    entry = MockConfigEntry(
        title="OpenRouter",
        domain=DOMAIN,
        data={CONF_API_KEY: "bla"},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_MODEL: "openai/gpt-4o-mini-tts",
                    "supported_voices": ["alloy", "echo"],
                    CONF_TTS_VOICE: "alloy",
                    CONF_TTS_SPEED: 1.0,
                },
                subentry_id="TTSSUB",
                subentry_type="tts",
                title="GPT-4o mini TTS",
                unique_id=None,
            ),
        ],
    )
    await setup_integration(hass, entry)

    tts_model = MagicMock()
    tts_model.id = "openai/gpt-4o-mini-tts"
    tts_model.name = "GPT-4o mini TTS"
    tts_model.supported_voices = ["alloy", "echo"]
    mock_open_router_client.get_models.return_value = [tts_model]

    result = await entry.start_subentry_reconfigure_flow(hass, "TTSSUB")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    # The stored model is offered as the default on reconfigure.
    model_key = next(k for k in result["data_schema"].schema if k == CONF_MODEL)
    assert model_key.default() == "openai/gpt-4o-mini-tts"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "openai/gpt-4o-mini-tts"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "voice"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_TTS_VOICE: "echo", CONF_TTS_SPEED: 1.5},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    subentry = entry.subentries["TTSSUB"]
    assert subentry.data[CONF_TTS_VOICE] == "echo"
    assert subentry.data[CONF_TTS_SPEED] == 1.5


@pytest.mark.usefixtures("mock_openai_client")
async def test_reconfigure_stt_service(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
) -> None:
    """Test reconfiguring an STT service."""
    entry = MockConfigEntry(
        title="OpenRouter",
        domain=DOMAIN,
        data={CONF_API_KEY: "bla"},
        subentries_data=[
            ConfigSubentryData(
                data={CONF_MODEL: "openai/whisper-large-v3"},
                subentry_id="STTSUB",
                subentry_type="stt",
                title="Whisper Large v3",
                unique_id=None,
            ),
        ],
    )
    await setup_integration(hass, entry)

    stt_model = MagicMock()
    stt_model.id = "openai/whisper-large-v3"
    stt_model.name = "Whisper Large v3"
    stt_model_2 = MagicMock()
    stt_model_2.id = "some/other-stt"
    stt_model_2.name = "Other STT"
    mock_open_router_client.get_models.return_value = [stt_model, stt_model_2]

    result = await entry.start_subentry_reconfigure_flow(hass, "STTSUB")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "some/other-stt"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    subentry = entry.subentries["STTSUB"]
    assert subentry.data[CONF_MODEL] == "some/other-stt"


async def test_reconfigure_conversation_agent(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring a conversation agent."""
    await setup_integration(hass, mock_config_entry)

    subentry_id = get_subentry_id(mock_config_entry, "conversation")

    # Now reconfigure it
    result = await mock_config_entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Update the configuration
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "openai/gpt-4",
            CONF_PROMPT: "updated prompt",
            CONF_LLM_HASS_API: ["assist"],
            CONF_WEB_SEARCH: True,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    subentry = mock_config_entry.subentries[subentry_id]
    assert subentry.data[CONF_MODEL] == "openai/gpt-4"
    assert subentry.data[CONF_PROMPT] == "updated prompt"
    assert subentry.data[CONF_LLM_HASS_API] == ["assist"]
    assert subentry.data[CONF_WEB_SEARCH] is True


async def test_reconfigure_ai_task(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring an AI task."""
    await setup_integration(hass, mock_config_entry)

    subentry_id = get_subentry_id(mock_config_entry, "ai_task_data")

    result = await mock_config_entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Update the configuration
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "openai/gpt-4"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    "subentry_type",
    ["conversation", "ai_task_data", "tts", "stt"],
)
async def test_reconfigure_entry_not_loaded(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    subentry_type: str,
) -> None:
    """Test starting a subentry flow while the entry is not loaded aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, subentry_type),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [(OpenRouterError("exception"), "cannot_connect"), (Exception, "unknown")],
)
async def test_reconfigure_conversation_agent_abort(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    reason: str,
) -> None:
    """Test reconfiguring a conversation agent with error and recovery."""
    await setup_integration(hass, mock_config_entry)

    subentry_id = get_subentry_id(mock_config_entry, "conversation")

    mock_open_router_client.get_models.side_effect = exception

    result = await mock_config_entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize(
    ("exception", "reason"),
    [(OpenRouterError("exception"), "cannot_connect"), (Exception, "unknown")],
)
async def test_reconfigure_ai_task_abort(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    reason: str,
) -> None:
    """Test reconfiguring an AI task with error and recovery."""
    await setup_integration(hass, mock_config_entry)

    subentry_id = get_subentry_id(mock_config_entry, "ai_task_data")

    # Trigger an error during reconfiguration
    mock_open_router_client.get_models.side_effect = exception

    result = await mock_config_entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize(
    ("web_search", "expected_web_search"),
    [(True, True), (False, False)],
    indirect=["web_search"],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_create_conversation_agent_web_search(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    web_search: bool,
    expected_web_search: bool,
) -> None:
    """Test creating a conversation agent with web search enabled/disabled."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Verify web_search field is present in schema with correct default
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == CONF_WEB_SEARCH)
    assert key.default() is False

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "openai/gpt-3.5-turbo",
            CONF_PROMPT: "you are an assistant",
            CONF_LLM_HASS_API: ["assist"],
            CONF_WEB_SEARCH: expected_web_search,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_WEB_SEARCH] is expected_web_search


@pytest.mark.parametrize(
    ("current_web_search", "expected_default"),
    [(True, True), (False, False)],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_conversation_subentry_web_search_default(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    current_web_search: bool,
    expected_default: bool,
) -> None:
    """Test web_search field default reflects existing value when reconfiguring."""
    await setup_integration(hass, mock_config_entry)

    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_WEB_SEARCH: current_web_search},
    )
    await hass.async_block_till_done()

    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    schema = result["data_schema"].schema
    key = next(k for k in schema if k == CONF_WEB_SEARCH)
    assert key.default() is expected_default


@pytest.mark.parametrize(
    ("current_llm_apis", "suggested_llm_apis", "expected_options"),
    [
        (["assist"], ["assist"], ["assist"]),
        (["non-existent"], [], ["assist"]),
        (["assist", "non-existent"], ["assist"], ["assist"]),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_conversation_subentry_llm_api_schema(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    current_llm_apis: list[str],
    suggested_llm_apis: list[str],
    expected_options: list[str],
) -> None:
    """Test llm_hass_api field values when reconfiguring a conversation subentry."""
    await setup_integration(hass, mock_config_entry)

    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_LLM_HASS_API: current_llm_apis},
    )
    await hass.async_block_till_done()

    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Only valid LLM APIs should be suggested and shown as options
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == CONF_LLM_HASS_API)

    assert key.default() == suggested_llm_apis

    field_schema = schema[key]
    assert field_schema.config
    assert [
        opt["value"] for opt in field_schema.config.get("options")
    ] == expected_options
