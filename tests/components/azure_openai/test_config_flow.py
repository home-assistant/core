"""Test the Azure OpenAI config flow."""

import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
from openai import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from openai.types.responses import Response, ResponseOutputMessage, ResponseOutputText
from probatio import to_field_list
import pytest

from homeassistant import config_entries
from homeassistant.components.azure_openai.capabilities import get_capabilities
from homeassistant.components.azure_openai.client import normalize_base_url
from homeassistant.components.azure_openai.config_flow import validate_input
from homeassistant.components.azure_openai.const import (
    CONF_BASE_URL,
    CONF_CHAT_MODEL,
    CONF_CODE_INTERPRETER,
    CONF_IMAGE_DEPLOYMENT,
    CONF_IMAGE_MODEL,
    CONF_MAX_TOKENS,
    CONF_MODEL_FAMILY,
    CONF_PRO_MODE,
    CONF_REASONING_EFFORT,
    CONF_REASONING_SUMMARY,
    CONF_RECOMMENDED,
    CONF_STT_MODEL,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_TTS_MODEL,
    CONF_TTS_SPEED,
    CONF_VERBOSITY,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_INLINE_CITATIONS,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_STT_NAME,
    DEFAULT_TTS_NAME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_REASONING_SUMMARY,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TTS_OPTIONS,
)
from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigFlowResult,
    ConfigSubentry,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_VERSION,
    CONF_LLM_HASS_API,
    CONF_NAME,
    CONF_PROMPT,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import config_validation as cv

from .conftest import MOCK_CHAT_MODEL_FAMILY

from tests.common import MockConfigEntry

USER_DATA = {
    CONF_API_KEY: "bla",
    CONF_BASE_URL: "https://example.openai.azure.com",
    "conversation": {},
    "ai_task_data": {},
    "stt": {},
    "tts": {},
}


def _get_subentry(entry: MockConfigEntry, subentry_type: str) -> ConfigSubentry:
    """Return a subentry by type."""
    return next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == subentry_type
    )


async def _start_user_flow(hass: HomeAssistant) -> ConfigFlowResult:
    """Start the user config flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def _configure_user_flow(
    hass: HomeAssistant,
    flow_id: str,
    user_input: dict[str, Any],
) -> ConfigFlowResult:
    """Submit a user config flow step."""
    return await hass.config_entries.flow.async_configure(flow_id, user_input)


async def _configure_subentry_flow(
    hass: HomeAssistant,
    flow_id: str,
    user_input: dict[str, Any],
) -> SubentryFlowResult:
    """Submit a subentry config flow step."""
    return await hass.config_entries.subentries.async_configure(flow_id, user_input)


async def _configure_conversation_init(
    hass: HomeAssistant,
    flow_id: str,
    *,
    recommended: bool,
    chat_model: str,
    model_family: str,
    prompt: str | None = None,
    llm_hass_api: list[str] | None = None,
    name: str | None = None,
) -> SubentryFlowResult:
    """Configure the conversation init step."""
    user_input: dict[str, Any] = {
        CONF_RECOMMENDED: recommended,
        CONF_CHAT_MODEL: chat_model,
        CONF_MODEL_FAMILY: model_family,
    }
    if name is not None:
        user_input[CONF_NAME] = name
    if prompt is not None:
        user_input[CONF_PROMPT] = prompt
    if llm_hass_api is not None:
        user_input[CONF_LLM_HASS_API] = llm_hass_api
    return await _configure_subentry_flow(hass, flow_id, user_input)


async def _configure_ai_task_init(
    hass: HomeAssistant,
    flow_id: str,
    *,
    recommended: bool,
    chat_model: str,
    model_family: str,
    name: str | None = None,
) -> SubentryFlowResult:
    """Configure the AI task init step."""
    user_input: dict[str, Any] = {
        CONF_RECOMMENDED: recommended,
        CONF_CHAT_MODEL: chat_model,
        CONF_MODEL_FAMILY: model_family,
    }
    if name is not None:
        user_input[CONF_NAME] = name
    return await _configure_subentry_flow(hass, flow_id, user_input)


def _section_schema(result: SubentryFlowResult, section_name: str) -> dict[Any, Any]:
    """Return a section's inner schema."""
    return result["data_schema"].schema[section_name].schema.schema


async def _configure_model(
    hass: HomeAssistant,
    flow_id: str,
    result: SubentryFlowResult,
    *,
    values: dict[str, Any] | None = None,
) -> SubentryFlowResult:
    """Configure the sectioned model options step."""
    user_input: dict[str, dict[str, Any]] = {}
    for section_key, section_value in result["data_schema"].schema.items():
        section_name = section_key.schema
        user_input[section_name] = section_value.schema({})
        for key, value in (values or {}).items():
            if key in section_value.schema.schema:
                user_input[section_name][key] = value
    return await _configure_subentry_flow(hass, flow_id, user_input)


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        (
            "https://example.openai.azure.com",
            "https://example.openai.azure.com/openai/v1/",
        ),
        (
            "https://example.openai.azure.us/",
            "https://example.openai.azure.us/openai/v1/",
        ),
        (
            "https://example.services.ai.azure.com",
            "https://example.services.ai.azure.com/openai/v1/",
        ),
        (
            "https://EXAMPLE.openai.azure.com/openai/v1",
            "https://example.openai.azure.com/openai/v1/",
        ),
        (
            "https://example.openai.azure.com/deployments/foo",
            "https://example.openai.azure.com/deployments/foo",
        ),
        ("https://example.com", "https://example.com"),
    ],
)
def test_normalize_base_url(
    base_url: str,
    expected: str,
) -> None:
    """Test Azure resource URL normalization."""
    assert normalize_base_url(base_url) == expected


def test_unknown_model_family_uses_basic_capabilities() -> None:
    """Test an unknown family falls back to conservative capabilities."""
    capabilities = get_capabilities("my-custom-family")

    assert capabilities.features == frozenset({"sampling"})
    assert capabilities.reasoning == ()
    assert capabilities.reasoning_summary == []
    assert capabilities.supports_sampling() is True


async def test_form_creates_entry_without_optional_subentries(
    hass: HomeAssistant,
) -> None:
    """Test creating a config entry without any onboarding subentries."""
    result = await _start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)

    with (
        patch(
            "homeassistant.components.azure_openai.config_flow.validate_input",
            new=AsyncMock(),
        ) as mock_validate_input,
        patch(
            "homeassistant.components.azure_openai.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await _configure_user_flow(hass, result["flow_id"], USER_DATA)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Azure OpenAI"
    assert result["data"] == {
        CONF_API_KEY: "bla",
        CONF_BASE_URL: "https://example.openai.azure.com/openai/v1/",
    }
    assert result["subentries"] == ()
    mock_validate_input.assert_awaited_once_with(
        hass,
        {
            CONF_API_KEY: "bla",
            CONF_BASE_URL: "https://example.openai.azure.com/openai/v1/",
        },
    )
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_creates_entry_with_conversation_and_ai_task(
    hass: HomeAssistant,
) -> None:
    """Test creating a config entry with conversation and AI task subentries."""
    result = await _start_user_flow(hass)

    with (
        patch(
            "homeassistant.components.azure_openai.config_flow.validate_input",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.azure_openai.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await _configure_user_flow(
            hass,
            result["flow_id"],
            {
                **USER_DATA,
                "conversation": {
                    CONF_CHAT_MODEL: "conversation-deployment",
                    CONF_MODEL_FAMILY: "gpt-5",
                },
                "ai_task_data": {
                    CONF_CHAT_MODEL: "ai-task-deployment",
                    CONF_MODEL_FAMILY: "gpt-5",
                },
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: "bla",
        CONF_BASE_URL: "https://example.openai.azure.com/openai/v1/",
    }
    assert result["subentries"] == [
        {
            "subentry_type": "conversation",
            "data": {
                **RECOMMENDED_CONVERSATION_OPTIONS,
                CONF_CHAT_MODEL: "conversation-deployment",
                CONF_MODEL_FAMILY: "gpt-5",
            },
            "title": DEFAULT_CONVERSATION_NAME,
            "unique_id": None,
        },
        {
            "subentry_type": "ai_task_data",
            "data": {
                **RECOMMENDED_AI_TASK_OPTIONS,
                CONF_CHAT_MODEL: "ai-task-deployment",
                CONF_MODEL_FAMILY: "gpt-5",
            },
            "title": DEFAULT_AI_TASK_NAME,
            "unique_id": None,
        },
    ]


async def test_form_creates_all_optional_subentries(
    hass: HomeAssistant,
) -> None:
    """Test creating every supported onboarding subentry."""
    result = await _start_user_flow(hass)

    with (
        patch(
            "homeassistant.components.azure_openai.config_flow.validate_input",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.azure_openai.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await _configure_user_flow(
            hass,
            result["flow_id"],
            {
                **USER_DATA,
                "conversation": {
                    CONF_CHAT_MODEL: "chat-deployment",
                    CONF_MODEL_FAMILY: "gpt-5.6-sol",
                },
                "ai_task_data": {
                    CONF_CHAT_MODEL: "chat-deployment",
                    CONF_MODEL_FAMILY: "gpt-5.6-sol",
                },
                "stt": {
                    CONF_CHAT_MODEL: "stt-deployment",
                    CONF_STT_MODEL: "gpt-4o-transcribe",
                },
                "tts": {
                    CONF_CHAT_MODEL: "tts-deployment",
                    CONF_TTS_MODEL: "gpt-4o-mini-tts",
                },
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["subentries"] == [
        {
            "subentry_type": "conversation",
            "data": {
                **RECOMMENDED_CONVERSATION_OPTIONS,
                CONF_CHAT_MODEL: "chat-deployment",
                CONF_MODEL_FAMILY: "gpt-5.6-sol",
            },
            "title": DEFAULT_CONVERSATION_NAME,
            "unique_id": None,
        },
        {
            "subentry_type": "ai_task_data",
            "data": {
                **RECOMMENDED_AI_TASK_OPTIONS,
                CONF_CHAT_MODEL: "chat-deployment",
                CONF_MODEL_FAMILY: "gpt-5.6-sol",
            },
            "title": DEFAULT_AI_TASK_NAME,
            "unique_id": None,
        },
        {
            "subentry_type": "stt",
            "data": {
                **RECOMMENDED_STT_OPTIONS,
                CONF_CHAT_MODEL: "stt-deployment",
                CONF_STT_MODEL: "gpt-4o-transcribe",
            },
            "title": DEFAULT_STT_NAME,
            "unique_id": None,
        },
        {
            "subentry_type": "tts",
            "data": {
                **RECOMMENDED_TTS_OPTIONS,
                CONF_CHAT_MODEL: "tts-deployment",
                CONF_TTS_MODEL: "gpt-4o-mini-tts",
            },
            "title": DEFAULT_TTS_NAME,
            "unique_id": None,
        },
    ]


@pytest.mark.parametrize(
    "section_input",
    [
        pytest.param(
            {CONF_CHAT_MODEL: "conversation-deployment"},
            id="deployment-only",
        ),
        pytest.param(
            {CONF_MODEL_FAMILY: "gpt-5"},
            id="family-only",
        ),
    ],
)
async def test_form_requires_complete_conversation_routing(
    hass: HomeAssistant,
    section_input: dict[str, str],
) -> None:
    """Test the conversation section requires both deployment and family."""
    result = await _start_user_flow(hass)

    with patch(
        "homeassistant.components.azure_openai.config_flow.validate_input",
        new=AsyncMock(),
    ) as mock_validate_input:
        result = await _configure_user_flow(
            hass,
            result["flow_id"],
            {**USER_DATA, "conversation": section_input},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "deployment_model_family_required"}
    assert mock_validate_input.await_count == 0


@pytest.mark.parametrize(
    "section_input",
    [
        pytest.param(
            {CONF_CHAT_MODEL: "stt-deployment"},
            id="deployment-only",
        ),
        pytest.param(
            {CONF_STT_MODEL: "whisper"},
            id="model-only",
        ),
    ],
)
async def test_form_requires_complete_stt_routing(
    hass: HomeAssistant,
    section_input: dict[str, str],
) -> None:
    """Test the STT section requires both deployment and model."""
    result = await _start_user_flow(hass)

    with patch(
        "homeassistant.components.azure_openai.config_flow.validate_input",
        new=AsyncMock(),
    ) as mock_validate_input:
        result = await _configure_user_flow(
            hass,
            result["flow_id"],
            {**USER_DATA, "stt": section_input},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "stt_deployment_model_required"}
    assert mock_validate_input.await_count == 0


@pytest.mark.parametrize(
    "section_input",
    [
        pytest.param(
            {CONF_CHAT_MODEL: "tts-deployment"},
            id="deployment-only",
        ),
        pytest.param(
            {CONF_TTS_MODEL: "gpt-4o-mini-tts"},
            id="model-only",
        ),
    ],
)
async def test_form_requires_complete_tts_routing(
    hass: HomeAssistant,
    section_input: dict[str, str],
) -> None:
    """Test the TTS section requires both deployment and model."""
    result = await _start_user_flow(hass)

    with patch(
        "homeassistant.components.azure_openai.config_flow.validate_input",
        new=AsyncMock(),
    ) as mock_validate_input:
        result = await _configure_user_flow(
            hass,
            result["flow_id"],
            {**USER_DATA, "tts": section_input},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "tts_deployment_model_required"}
    assert mock_validate_input.await_count == 0


async def test_form_stores_stt_api_version_override(
    hass: HomeAssistant,
) -> None:
    """Test the STT section stores a manual api-version override."""
    result = await _start_user_flow(hass)

    with patch(
        "homeassistant.components.azure_openai.config_flow.validate_input",
        new=AsyncMock(),
    ):
        result = await _configure_user_flow(
            hass,
            result["flow_id"],
            {
                **USER_DATA,
                "stt": {
                    CONF_CHAT_MODEL: "stt-deployment",
                    CONF_STT_MODEL: "whisper",
                    CONF_API_VERSION: "2025-01-01-preview",
                },
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    stt_subentry = next(
        subentry
        for subentry in result["subentries"]
        if subentry["subentry_type"] == "stt"
    )
    assert stt_subentry["data"][CONF_API_VERSION] == "2025-01-01-preview"


async def test_form_rejects_unsupported_model_family(
    hass: HomeAssistant,
) -> None:
    """Test the conversation section rejects unsupported model families."""
    result = await _start_user_flow(hass)

    with patch(
        "homeassistant.components.azure_openai.config_flow.validate_input",
        new=AsyncMock(),
    ) as mock_validate_input:
        result = await _configure_user_flow(
            hass,
            result["flow_id"],
            {
                **USER_DATA,
                "conversation": {
                    CONF_CHAT_MODEL: "starter-deployment",
                    CONF_MODEL_FAMILY: "o1-mini",
                },
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "model_not_supported"}
    assert mock_validate_input.await_count == 0


@pytest.mark.parametrize(
    ("deployment", "model_family", "error"),
    [
        pytest.param(
            "ai-task-deployment",
            "",
            "deployment_model_family_required",
            id="missing-family",
        ),
        pytest.param(
            "ai-task-deployment",
            "o1-mini",
            "model_not_supported",
            id="unsupported-family",
        ),
    ],
)
async def test_form_validates_ai_task_model_family(
    hass: HomeAssistant,
    deployment: str,
    model_family: str,
    error: str,
) -> None:
    """Test the AI Task section validates deployment and model family."""
    result = await _start_user_flow(hass)

    with patch(
        "homeassistant.components.azure_openai.config_flow.validate_input",
        new=AsyncMock(),
    ) as mock_validate_input:
        result = await _configure_user_flow(
            hass,
            result["flow_id"],
            {
                **USER_DATA,
                "ai_task_data": {
                    CONF_CHAT_MODEL: deployment,
                    CONF_MODEL_FAMILY: model_family,
                },
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert mock_validate_input.await_count == 0


async def test_duplicate_entry_matches_normalized_base_url(
    hass: HomeAssistant,
) -> None:
    """Test duplicate detection uses normalized connection data."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "different-key",
            CONF_BASE_URL: "https://EXAMPLE.openai.azure.com/openai/v1",
        },
    ).add_to_hass(hass)

    result = await _start_user_flow(hass)

    with patch(
        "homeassistant.components.azure_openai.config_flow.validate_input",
        new=AsyncMock(),
    ):
        result = await _configure_user_flow(hass, result["flow_id"], USER_DATA)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_validate_input(hass: HomeAssistant) -> None:
    """Test validating connection data."""
    client = AsyncMock()
    with patch(
        "homeassistant.components.azure_openai.config_flow.create_client",
        return_value=client,
    ):
        await validate_input(hass, USER_DATA)

    client.models.list.assert_awaited_once_with(timeout=10.0)


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(APIConnectionError(request=None), "cannot_connect", id="connect"),
        pytest.param(
            AuthenticationError(
                response=httpx.Response(
                    status_code=401, request=httpx.Request("GET", "https://example.com")
                ),
                body=None,
                message=None,
            ),
            "invalid_auth",
            id="auth",
        ),
        pytest.param(
            BadRequestError(
                response=httpx.Response(
                    status_code=400, request=httpx.Request("GET", "https://example.com")
                ),
                body=None,
                message=None,
            ),
            "unknown",
            id="unknown",
        ),
    ],
)
async def test_form_invalid_auth(
    hass: HomeAssistant,
    side_effect: Exception,
    error: str,
) -> None:
    """Test validation errors on the main user flow."""
    result = await _start_user_flow(hass)

    with patch(
        "homeassistant.components.azure_openai.config_flow.validate_input",
        new=AsyncMock(side_effect=side_effect),
    ):
        result = await _configure_user_flow(hass, result["flow_id"], USER_DATA)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_form_rejects_blank_base_url(hass: HomeAssistant) -> None:
    """Test a whitespace-only base URL is rejected."""
    result = await _start_user_flow(hass)

    result = await _configure_user_flow(
        hass, result["flow_id"], {**USER_DATA, CONF_BASE_URL: " "}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BASE_URL: "base_url_required"}


async def test_reauth_updates_connection_data(
    hass: HomeAssistant,
) -> None:
    """Test reauthentication updates the config entry data."""
    hass.config.components.add(DOMAIN)
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "old_api_key",
            CONF_BASE_URL: "https://OLD.openai.azure.com/openai/v1",
        },
        state=ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.azure_openai.config_flow.validate_input",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as mock_async_reload,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "new_api_key",
                CONF_BASE_URL: "https://old.openai.azure.com",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_API_KEY: "new_api_key",
        CONF_BASE_URL: "https://old.openai.azure.com/openai/v1/",
    }
    assert mock_async_reload.call_count == 1


@pytest.mark.parametrize(
    "source",
    [config_entries.SOURCE_REAUTH, config_entries.SOURCE_RECONFIGURE],
)
async def test_connection_update_recovers_from_invalid_auth(
    hass: HomeAssistant,
    source: str,
) -> None:
    """Test connection update flows recover from invalid credentials."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "old_api_key",
            CONF_BASE_URL: "https://old.openai.azure.com/openai/v1/",
        },
        state=ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    if source == config_entries.SOURCE_REAUTH:
        result = await mock_config_entry.start_reauth_flow(hass)
    else:
        result = await mock_config_entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.azure_openai.config_flow.validate_input",
        new=AsyncMock(
            side_effect=AuthenticationError(
                response=httpx.Response(
                    status_code=401, request=httpx.Request("GET", "https://example.com")
                ),
                body=None,
                message=None,
            )
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "invalid_api_key",
                CONF_BASE_URL: "https://new.openai.azure.com",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == (
        "reauth_confirm" if source == config_entries.SOURCE_REAUTH else "reconfigure"
    )
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.usefixtures("mock_init_component")
async def test_reconfigure_updates_connection_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration updates the config entry data."""
    result = await mock_config_entry.start_reconfigure_flow(hass)
    with (
        patch(
            "homeassistant.components.azure_openai.config_flow.validate_input",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as mock_async_reload,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "new_api_key",
                CONF_BASE_URL: "https://new.openai.azure.com",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_API_KEY: "new_api_key",
        CONF_BASE_URL: "https://new.openai.azure.com/openai/v1/",
    }
    assert mock_async_reload.call_count == 1


async def test_creating_conversation_subentry_recommended(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a recommended conversation subentry."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {}
    assert to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)

    result = await _configure_conversation_init(
        hass,
        result["flow_id"],
        name="My Custom Agent",
        prompt="Speak like a pirate",
        llm_hass_api=["assist"],
        recommended=True,
        chat_model=" custom-deployment ",
        model_family=" gpt-5.1 ",
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Custom Agent"
    assert result["data"] == {
        CONF_PROMPT: "Speak like a pirate",
        CONF_LLM_HASS_API: ["assist"],
        CONF_RECOMMENDED: True,
        CONF_CHAT_MODEL: "custom-deployment",
        CONF_MODEL_FAMILY: "gpt-5.1",
    }


async def test_creating_conversation_subentry_rejects_blank_deployment(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a conversation subentry requires a deployment name."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await _configure_conversation_init(
        hass,
        result["flow_id"],
        recommended=True,
        chat_model="   ",
        model_family="gpt-5.1",
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {CONF_CHAT_MODEL: "deployment_required"}


async def test_creating_conversation_subentry_not_loaded(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation subentry when the parent entry is not loaded."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def test_conversation_subentry_recommended_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test reconfiguring a conversation subentry with recommended settings."""
    subentry = _get_subentry(mock_config_entry, "conversation")

    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await _configure_conversation_init(
        hass,
        subentry_flow["flow_id"],
        prompt="Speak like a pirate",
        llm_hass_api=["assist"],
        recommended=True,
        chat_model="new-deployment",
        model_family="gpt-5",
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data == {
        CONF_PROMPT: "Speak like a pirate",
        CONF_LLM_HASS_API: ["assist"],
        CONF_RECOMMENDED: True,
        CONF_CHAT_MODEL: "new-deployment",
        CONF_MODEL_FAMILY: "gpt-5",
    }


async def test_conversation_advanced_reconfigure_clears_optional_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test advanced reconfiguration clears omitted optional values."""
    subentry = _get_subentry(mock_config_entry, "conversation")
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: ["assist"],
        },
    )
    await hass.async_block_till_done()

    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await _configure_conversation_init(
        hass,
        subentry_flow["flow_id"],
        recommended=False,
        chat_model="new-deployment",
        model_family="gpt-5",
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    result = await _configure_model(
        hass,
        subentry_flow["flow_id"],
        result,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data[CONF_PROMPT] == ""
    assert CONF_LLM_HASS_API not in subentry.data


@pytest.mark.parametrize(
    ("model_family", "error"),
    [
        pytest.param("", "model_family_required", id="missing"),
        pytest.param("o1-mini", "model_not_supported", id="unsupported"),
    ],
)
async def test_conversation_subentry_requires_supported_model_family(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    model_family: str,
    error: str,
) -> None:
    """Test the conversation init step validates the model family."""
    subentry = _get_subentry(mock_config_entry, "conversation")
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    result = await _configure_conversation_init(
        hass,
        subentry_flow["flow_id"],
        prompt="Speak like a pirate",
        recommended=False,
        chat_model="custom-deployment",
        model_family=model_family,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {CONF_MODEL_FAMILY: error}


@pytest.mark.parametrize(
    ("model_family", "reasoning_effort_options"),
    [
        pytest.param("o4-mini", ["low", "medium", "high"], id="o4-mini"),
        pytest.param(
            "gpt-5",
            ["minimal", "low", "medium", "high"],
            id="gpt-5",
        ),
        pytest.param(
            "gpt-5.1",
            ["none", "low", "medium", "high"],
            id="gpt-5.1",
        ),
        pytest.param(
            "gpt-5.2",
            ["none", "low", "medium", "high", "xhigh"],
            id="gpt-5.2",
        ),
        pytest.param(
            "gpt-5.6-sol",
            ["none", "low", "medium", "high", "xhigh", "max"],
            id="gpt-5.6-sol",
        ),
        pytest.param(
            "gpt-6-astra",
            ["low", "medium", "high", "xhigh", "max"],
            id="gpt-6-astra",
        ),
    ],
)
async def test_conversation_subentry_reasoning_effort_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    model_family: str,
    reasoning_effort_options: list[str],
) -> None:
    """Test reasoning effort choices are derived from the declared model family."""
    subentry = _get_subentry(mock_config_entry, "conversation")
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    result = await _configure_conversation_init(
        hass,
        subentry_flow["flow_id"],
        prompt="Speak like a pirate",
        llm_hass_api=["assist"],
        recommended=False,
        chat_model="custom-deployment",
        model_family=model_family,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"
    assert (
        _section_schema(result, "reasoning")[CONF_REASONING_EFFORT].config["options"]
        == reasoning_effort_options
    )


@pytest.mark.parametrize(
    ("model_family", "expected_reasoning_summary"),
    [
        pytest.param("o4-mini", ["off", "auto", "detailed"], id="o4-mini"),
        pytest.param("gpt-5", ["off", "auto", "detailed"], id="gpt-5"),
        pytest.param("gpt-6-astra", ["off", "auto", "detailed"], id="gpt-6"),
    ],
)
async def test_conversation_subentry_reasoning_summary_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    model_family: str,
    expected_reasoning_summary: list[str],
) -> None:
    """Test reasoning summary options are driven by the model family."""
    subentry = _get_subentry(mock_config_entry, "conversation")
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    result = await _configure_conversation_init(
        hass,
        subentry_flow["flow_id"],
        prompt="Speak like a pirate",
        recommended=False,
        chat_model="custom-deployment",
        model_family=model_family,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"
    assert (
        _section_schema(result, "reasoning")[CONF_REASONING_SUMMARY].config["options"]
        == expected_reasoning_summary
    )


@pytest.mark.parametrize("model_family", ["gpt-4o", "gpt-4.1"])
async def test_conversation_subentry_hides_unsupported_reasoning_summary(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    model_family: str,
) -> None:
    """Test models without reasoning summaries do not show the setting."""
    subentry = _get_subentry(mock_config_entry, "conversation")
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    result = await _configure_conversation_init(
        hass,
        subentry_flow["flow_id"],
        prompt="Speak like a pirate",
        recommended=False,
        chat_model="custom-deployment",
        model_family=model_family,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"
    assert "reasoning" not in result["data_schema"].schema


async def test_conversation_subentry_reasoning_summary_default_is_sanitized(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test an invalid stored reasoning summary falls back to the recommended value."""
    subentry = _get_subentry(mock_config_entry, "conversation")
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_REASONING_SUMMARY: "concise",
        },
    )
    await hass.async_block_till_done()

    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await _configure_conversation_init(
        hass,
        subentry_flow["flow_id"],
        prompt="Speak like a pirate",
        recommended=False,
        chat_model="custom-deployment",
        model_family="gpt-5",
    )
    assert result["step_id"] == "model"

    summary_key = next(
        key
        for key in _section_schema(result, "reasoning")
        if key == CONF_REASONING_SUMMARY
    )
    assert summary_key.default() == RECOMMENDED_REASONING_SUMMARY


@pytest.mark.parametrize(
    ("parameter", "error"),
    [
        pytest.param(
            CONF_WEB_SEARCH,
            "web_search_minimal_reasoning",
            id="web-search",
        ),
        pytest.param(
            CONF_CODE_INTERPRETER,
            "code_interpreter_minimal_reasoning",
            id="code-interpreter",
        ),
    ],
)
async def test_conversation_subentry_rejects_minimal_reasoning_conflicts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    parameter: str,
    error: str,
) -> None:
    """Test model-step validation for minimal reasoning conflicts."""
    subentry = _get_subentry(mock_config_entry, "conversation")
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await _configure_conversation_init(
        hass,
        subentry_flow["flow_id"],
        prompt="Speak like a pirate",
        recommended=False,
        chat_model="custom-deployment",
        model_family="gpt-5",
    )
    assert result["step_id"] == "model"

    result = await _configure_model(
        hass,
        subentry_flow["flow_id"],
        result,
        values={
            CONF_REASONING_EFFORT: "minimal",
            parameter: True,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {parameter: error}

    result = await _configure_model(
        hass,
        subentry_flow["flow_id"],
        result,
        values={
            CONF_REASONING_EFFORT: "low",
            parameter: True,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_conversation_subentry_unknown_family_removes_gated_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test an unknown family falls back to basic chat and sampling options."""
    subentry = _get_subentry(mock_config_entry, "conversation")
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_CHAT_MODEL: "old-deployment",
            CONF_MODEL_FAMILY: "gpt-5.6-sol",
            CONF_MAX_TOKENS: 1200,
            CONF_CODE_INTERPRETER: True,
            CONF_REASONING_EFFORT: "max",
            CONF_REASONING_SUMMARY: "detailed",
            CONF_PRO_MODE: True,
            CONF_VERBOSITY: "high",
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
            CONF_WEB_SEARCH_USER_LOCATION: False,
            CONF_WEB_SEARCH_INLINE_CITATIONS: True,
        },
    )
    await hass.async_block_till_done()

    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await _configure_conversation_init(
        hass,
        subentry_flow["flow_id"],
        prompt="Speak like a pirate",
        recommended=False,
        chat_model="custom-deployment",
        model_family="my-custom-family",
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    result = await _configure_model(
        hass,
        subentry_flow["flow_id"],
        result,
        values={CONF_MAX_TOKENS: 900},
    )
    assert result["step_id"] == "sampling"

    result = await _configure_subentry_flow(
        hass,
        subentry_flow["flow_id"],
        {
            CONF_TOP_P: 0.6,
            CONF_TEMPERATURE: 0.4,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data == {
        CONF_RECOMMENDED: False,
        CONF_PROMPT: "Speak like a pirate",
        CONF_CHAT_MODEL: "custom-deployment",
        CONF_MODEL_FAMILY: "my-custom-family",
        CONF_MAX_TOKENS: 900,
        CONF_TOP_P: 0.6,
        CONF_TEMPERATURE: 0.4,
    }


async def test_conversation_subentry_web_search_user_location_uses_deployment(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test location lookup uses the configured deployment name."""
    caplog.set_level(
        logging.DEBUG, logger="homeassistant.components.azure_openai.config_flow"
    )
    subentry = _get_subentry(mock_config_entry, "conversation")
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    result = await _configure_conversation_init(
        hass,
        subentry_flow["flow_id"],
        prompt="Speak like a pirate",
        recommended=False,
        chat_model="routing-deployment",
        model_family=MOCK_CHAT_MODEL_FAMILY,
    )
    assert result["step_id"] == "model"

    hass.config.country = "US"
    hass.config.time_zone = "America/Los_Angeles"
    hass.states.async_set(
        "zone.home", "0", {"latitude": 37.7749, "longitude": -122.4194}
    )

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.return_value = Response(
            object="response",
            id="resp_A",
            created_at=1700000000,
            model="routing-deployment",
            parallel_tool_calls=True,
            tool_choice="auto",
            tools=[],
            output=[
                ResponseOutputMessage(
                    type="message",
                    id="msg_A",
                    content=[
                        ResponseOutputText(
                            type="output_text",
                            text='{"city": "San Francisco", "region": "California"}',
                            annotations=[],
                        )
                    ],
                    role="assistant",
                    status="completed",
                )
            ],
        )

        result = await _configure_model(
            hass,
            subentry_flow["flow_id"],
            result,
            values={
                CONF_MAX_TOKENS: 1500,
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_CONTEXT_SIZE: "medium",
                CONF_WEB_SEARCH_USER_LOCATION: True,
                CONF_WEB_SEARCH_INLINE_CITATIONS: True,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sampling"
    assert mock_create.call_args.kwargs["model"] == "routing-deployment"
    assert mock_create.call_args.kwargs["store"] is False
    config_flow_logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == "homeassistant.components.azure_openai.config_flow"
    )
    assert "Location data lookup completed" in config_flow_logs
    assert "San Francisco" not in config_flow_logs
    assert "California" not in config_flow_logs
    assert "America/Los_Angeles" not in config_flow_logs
    assert (
        mock_create.call_args.kwargs["input"][0]["content"]
        == "Where are the following coordinates located: (37.7749, -122.4194)?"
    )

    result = await _configure_subentry_flow(
        hass,
        subentry_flow["flow_id"],
        {
            CONF_TOP_P: 0.9,
            CONF_TEMPERATURE: 0.7,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data == {
        CONF_RECOMMENDED: False,
        CONF_PROMPT: "Speak like a pirate",
        CONF_CHAT_MODEL: "routing-deployment",
        CONF_MODEL_FAMILY: MOCK_CHAT_MODEL_FAMILY,
        CONF_MAX_TOKENS: 1500,
        CONF_WEB_SEARCH: True,
        CONF_WEB_SEARCH_CONTEXT_SIZE: "medium",
        CONF_WEB_SEARCH_USER_LOCATION: True,
        CONF_WEB_SEARCH_CITY: "San Francisco",
        CONF_WEB_SEARCH_REGION: "California",
        CONF_WEB_SEARCH_COUNTRY: "US",
        CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
        CONF_WEB_SEARCH_INLINE_CITATIONS: True,
        CONF_CODE_INTERPRETER: False,
        CONF_TOP_P: 0.9,
        CONF_TEMPERATURE: 0.7,
    }


async def test_conversation_subentry_disabling_web_search_clears_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test stored location data is dropped when web search is turned off."""
    subentry = _get_subentry(mock_config_entry, "conversation")
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_CHAT_MODEL: "routing-deployment",
            CONF_MODEL_FAMILY: MOCK_CHAT_MODEL_FAMILY,
            CONF_MAX_TOKENS: 1500,
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_CONTEXT_SIZE: "medium",
            CONF_WEB_SEARCH_USER_LOCATION: True,
            CONF_WEB_SEARCH_CITY: "San Francisco",
            CONF_WEB_SEARCH_REGION: "California",
            CONF_WEB_SEARCH_COUNTRY: "US",
            CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
            CONF_WEB_SEARCH_INLINE_CITATIONS: True,
        },
    )
    await hass.async_block_till_done()

    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await _configure_conversation_init(
        hass,
        subentry_flow["flow_id"],
        prompt="Speak like a pirate",
        recommended=False,
        chat_model="routing-deployment",
        model_family=MOCK_CHAT_MODEL_FAMILY,
    )
    assert result["step_id"] == "model"

    result = await _configure_model(
        hass,
        subentry_flow["flow_id"],
        result,
        values={
            CONF_MAX_TOKENS: 1500,
            CONF_WEB_SEARCH: False,
            CONF_WEB_SEARCH_CONTEXT_SIZE: "medium",
            CONF_WEB_SEARCH_USER_LOCATION: True,
            CONF_WEB_SEARCH_INLINE_CITATIONS: True,
        },
    )
    assert result["step_id"] == "sampling"

    result = await _configure_subentry_flow(
        hass,
        subentry_flow["flow_id"],
        {
            CONF_TOP_P: 0.9,
            CONF_TEMPERATURE: 0.7,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data[CONF_WEB_SEARCH] is False
    assert CONF_WEB_SEARCH_CITY not in subentry.data
    assert CONF_WEB_SEARCH_REGION not in subentry.data
    assert CONF_WEB_SEARCH_COUNTRY not in subentry.data
    assert CONF_WEB_SEARCH_TIMEZONE not in subentry.data


@pytest.mark.parametrize(
    ("side_effect", "error", "reauth"),
    [
        pytest.param(
            APIConnectionError(request=None), "cannot_connect", False, id="connection"
        ),
        pytest.param(
            AuthenticationError(
                response=httpx.Response(
                    status_code=401,
                    request=httpx.Request("POST", "https://example.com"),
                ),
                body=None,
                message=None,
            ),
            "invalid_auth",
            True,
            id="authentication",
        ),
        pytest.param(
            RateLimitError(
                response=httpx.Response(
                    status_code=429,
                    request=httpx.Request("POST", "https://example.com"),
                ),
                body=None,
                message=None,
            ),
            "rate_limited",
            False,
            id="rate-limit",
        ),
        pytest.param(
            BadRequestError(
                response=httpx.Response(
                    status_code=400,
                    request=httpx.Request("POST", "https://example.com"),
                ),
                body=None,
                message=None,
            ),
            "location_lookup_failed",
            False,
            id="provider",
        ),
    ],
)
async def test_conversation_subentry_web_search_user_location_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    side_effect: Exception,
    error: str,
    reauth: bool,
) -> None:
    """Test location lookup API errors are shown in the subentry flow."""
    subentry = _get_subentry(mock_config_entry, "conversation")
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await _configure_conversation_init(
        hass,
        subentry_flow["flow_id"],
        prompt="Speak like a pirate",
        recommended=False,
        chat_model="routing-deployment",
        model_family=MOCK_CHAT_MODEL_FAMILY,
    )
    hass.states.async_set("zone.home", "0", {"latitude": 1.0, "longitude": 2.0})

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new=AsyncMock(side_effect=side_effect),
    ):
        result = await _configure_model(
            hass,
            subentry_flow["flow_id"],
            result,
            values={
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_USER_LOCATION: True,
            },
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"
    assert result["errors"] == {"base": error}
    reauth_flows = [
        flow
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if flow["context"]["source"] == config_entries.SOURCE_REAUTH
    ]
    assert bool(reauth_flows) is reauth


@pytest.mark.parametrize("output_text", ["not JSON", '{"city": 1}'])
async def test_conversation_subentry_web_search_user_location_invalid_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    output_text: str,
) -> None:
    """Test invalid location responses are shown in the subentry flow."""
    subentry = _get_subentry(mock_config_entry, "conversation")
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await _configure_conversation_init(
        hass,
        subentry_flow["flow_id"],
        prompt="Speak like a pirate",
        recommended=False,
        chat_model="routing-deployment",
        model_family=MOCK_CHAT_MODEL_FAMILY,
    )
    hass.states.async_set("zone.home", "0", {"latitude": 1.0, "longitude": 2.0})

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new=AsyncMock(
            return_value=Response(
                object="response",
                id="resp_A",
                created_at=1700000000,
                model="routing-deployment",
                parallel_tool_calls=True,
                tool_choice="auto",
                tools=[],
                output=[
                    ResponseOutputMessage(
                        type="message",
                        id="msg_A",
                        content=[
                            ResponseOutputText(
                                type="output_text",
                                text=output_text,
                                annotations=[],
                            )
                        ],
                        role="assistant",
                        status="completed",
                    )
                ],
            )
        ),
    ):
        result = await _configure_model(
            hass,
            subentry_flow["flow_id"],
            result,
            values={
                CONF_WEB_SEARCH: True,
                CONF_WEB_SEARCH_USER_LOCATION: True,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"
    assert result["errors"] == {"base": "location_lookup_failed"}


async def test_creating_ai_task_subentry_recommended(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test creating a recommended AI task subentry."""
    old_subentries = set(mock_config_entry.subentries)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_data"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)

    result = await _configure_ai_task_init(
        hass,
        result["flow_id"],
        name="Custom AI Task",
        recommended=True,
        chat_model="task-deployment",
        model_family="gpt-5.1",
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Custom AI Task"
    assert result["data"] == {
        CONF_RECOMMENDED: True,
        CONF_CHAT_MODEL: "task-deployment",
        CONF_MODEL_FAMILY: "gpt-5.1",
    }

    new_subentry_id = next(iter(set(mock_config_entry.subentries) - old_subentries))
    new_subentry = mock_config_entry.subentries[new_subentry_id]
    assert new_subentry.subentry_type == "ai_task_data"
    assert new_subentry.title == "Custom AI Task"


async def test_ai_task_subentry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating an AI task subentry when the parent entry is not loaded."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_data"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def test_creating_ai_task_subentry_advanced(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test creating an AI task subentry with gated model options."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_data"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["step_id"] == "init"

    result = await _configure_ai_task_init(
        hass,
        result["flow_id"],
        name="Advanced AI Task",
        recommended=False,
        chat_model="task-deployment",
        model_family="gpt-4o-mini",
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"
    image_generation_schema = _section_schema(result, "image_generation")
    assert list(image_generation_schema) == [
        CONF_IMAGE_DEPLOYMENT,
        CONF_IMAGE_MODEL,
    ]
    assert "web_search" not in result["data_schema"].schema

    result = await _configure_model(
        hass,
        result["flow_id"],
        result,
        values={
            CONF_MAX_TOKENS: 200,
            CONF_CODE_INTERPRETER: False,
            CONF_IMAGE_MODEL: " gpt-image-1-mini ",
            CONF_IMAGE_DEPLOYMENT: " custom-image-deployment ",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sampling"

    result = await _configure_subentry_flow(
        hass,
        result["flow_id"],
        {
            CONF_TOP_P: 0.9,
            CONF_TEMPERATURE: 0.5,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Advanced AI Task"
    assert result["data"] == {
        CONF_RECOMMENDED: False,
        CONF_CHAT_MODEL: "task-deployment",
        CONF_MODEL_FAMILY: "gpt-4o-mini",
        CONF_MAX_TOKENS: 200,
        CONF_CODE_INTERPRETER: False,
        CONF_IMAGE_MODEL: "gpt-image-1-mini",
        CONF_IMAGE_DEPLOYMENT: "custom-image-deployment",
        CONF_TOP_P: 0.9,
        CONF_TEMPERATURE: 0.5,
    }


async def test_creating_ai_task_subentry_without_image_deployment(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test creating an AI task subentry with an image-capable model, image off."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_data"),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await _configure_ai_task_init(
        hass,
        result["flow_id"],
        name="Text-Only AI Task",
        recommended=False,
        chat_model="task-deployment",
        model_family="gpt-4o-mini",
    )
    assert result["step_id"] == "model"
    assert CONF_IMAGE_DEPLOYMENT in _section_schema(result, "image_generation")

    result = await _configure_model(
        hass,
        result["flow_id"],
        result,
        values={
            CONF_MAX_TOKENS: 200,
            CONF_CODE_INTERPRETER: False,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sampling"

    result = await _configure_subentry_flow(
        hass,
        result["flow_id"],
        {CONF_TOP_P: 0.9, CONF_TEMPERATURE: 0.5},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_IMAGE_DEPLOYMENT not in result["data"]


async def test_creating_stt_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test creating an STT subentry."""
    old_subentries = set(mock_config_entry.subentries)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "stt"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)

    result = await _configure_subentry_flow(
        hass,
        result["flow_id"],
        {
            CONF_NAME: "Custom STT",
            CONF_PROMPT: "Transcribe pirate radio.",
            CONF_CHAT_MODEL: " stt-custom-deployment ",
            CONF_STT_MODEL: " gpt-4o-transcribe ",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Custom STT"
    assert result["data"] == {
        CONF_PROMPT: "Transcribe pirate radio.",
        CONF_CHAT_MODEL: "stt-custom-deployment",
        CONF_STT_MODEL: "gpt-4o-transcribe",
    }

    new_subentry_id = next(iter(set(mock_config_entry.subentries) - old_subentries))
    new_subentry = mock_config_entry.subentries[new_subentry_id]
    assert new_subentry.subentry_type == "stt"
    assert new_subentry.title == "Custom STT"


async def test_creating_stt_subentry_with_api_version_override(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test creating an STT subentry with a manual API version override."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "stt"),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await _configure_subentry_flow(
        hass,
        result["flow_id"],
        {
            CONF_NAME: "Custom STT",
            CONF_PROMPT: "Transcribe pirate radio.",
            CONF_CHAT_MODEL: "stt-custom-deployment",
            CONF_STT_MODEL: "gpt-4o-transcribe",
            CONF_API_VERSION: " 2025-01-01-preview ",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_PROMPT: "Transcribe pirate radio.",
        CONF_CHAT_MODEL: "stt-custom-deployment",
        CONF_STT_MODEL: "gpt-4o-transcribe",
        CONF_API_VERSION: "2025-01-01-preview",
    }


@pytest.mark.parametrize(
    ("subentry_type", "user_input", "error"),
    [
        pytest.param(
            "stt",
            {
                CONF_NAME: "Custom STT",
                CONF_CHAT_MODEL: "   ",
                CONF_STT_MODEL: "gpt-4o-transcribe",
            },
            {CONF_CHAT_MODEL: "deployment_required"},
            id="stt-deployment",
        ),
        pytest.param(
            "stt",
            {
                CONF_NAME: "Custom STT",
                CONF_CHAT_MODEL: "stt-deployment",
                CONF_STT_MODEL: "   ",
            },
            {CONF_STT_MODEL: "model_required"},
            id="stt-model",
        ),
        pytest.param(
            "tts",
            {
                CONF_NAME: "Custom TTS",
                CONF_CHAT_MODEL: "   ",
                CONF_TTS_MODEL: "gpt-4o-mini-tts",
                CONF_TTS_SPEED: 1.0,
            },
            {CONF_CHAT_MODEL: "deployment_required"},
            id="tts-deployment",
        ),
        pytest.param(
            "tts",
            {
                CONF_NAME: "Custom TTS",
                CONF_CHAT_MODEL: "tts-deployment",
                CONF_TTS_MODEL: "   ",
                CONF_TTS_SPEED: 1.0,
            },
            {CONF_TTS_MODEL: "model_required"},
            id="tts-model",
        ),
    ],
)
async def test_creating_speech_subentry_rejects_blank_identifiers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    subentry_type: str,
    user_input: dict[str, Any],
    error: dict[str, str],
) -> None:
    """Test speech subentries require deployment and model identifiers."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, subentry_type),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await _configure_subentry_flow(hass, result["flow_id"], user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == error


async def test_stt_subentry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating an STT subentry when the parent entry is not loaded."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "stt"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def test_stt_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test reconfiguring the STT subentry."""
    subentry = _get_subentry(mock_config_entry, "stt")
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    result = await _configure_subentry_flow(
        hass,
        subentry_flow["flow_id"],
        {
            CONF_PROMPT: "This is a conversation about smart pirate ships.",
            CONF_CHAT_MODEL: "transcription-deployment-v2",
            CONF_STT_MODEL: "gpt-4o-transcribe",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data == {
        CONF_CHAT_MODEL: "transcription-deployment-v2",
        CONF_PROMPT: "This is a conversation about smart pirate ships.",
        CONF_STT_MODEL: "gpt-4o-transcribe",
    }


async def test_stt_reconfigure_clears_optional_text(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test reconfiguring STT clears omitted optional text."""
    subentry = _get_subentry(mock_config_entry, "stt")
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_PROMPT: "Transcribe pirate radio.",
            CONF_API_VERSION: "2025-01-01-preview",
        },
    )
    await hass.async_block_till_done()
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    result = await _configure_subentry_flow(
        hass,
        subentry_flow["flow_id"],
        {
            CONF_CHAT_MODEL: "transcription-deployment-v2",
            CONF_STT_MODEL: "gpt-4o-transcribe",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data == {
        CONF_CHAT_MODEL: "transcription-deployment-v2",
        CONF_PROMPT: "",
        CONF_STT_MODEL: "gpt-4o-transcribe",
    }


async def test_creating_tts_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test creating a TTS subentry."""
    old_subentries = set(mock_config_entry.subentries)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "tts"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)

    result = await _configure_subentry_flow(
        hass,
        result["flow_id"],
        {
            CONF_NAME: "Custom TTS",
            CONF_CHAT_MODEL: " tts-custom-deployment ",
            CONF_TTS_MODEL: " tts-hd ",
            CONF_PROMPT: "Speak like a pirate",
            CONF_TTS_SPEED: 0.85,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Custom TTS"
    assert result["data"] == {
        CONF_CHAT_MODEL: "tts-custom-deployment",
        CONF_TTS_MODEL: "tts-hd",
        CONF_PROMPT: "Speak like a pirate",
        CONF_TTS_SPEED: 0.85,
    }

    new_subentry_id = next(iter(set(mock_config_entry.subentries) - old_subentries))
    new_subentry = mock_config_entry.subentries[new_subentry_id]
    assert new_subentry.subentry_type == "tts"
    assert new_subentry.title == "Custom TTS"


async def test_creating_tts_subentry_requires_nonempty_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test creating a TTS subentry rejects an empty model."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "tts"),
        context={"source": config_entries.SOURCE_USER},
    )

    with pytest.raises(InvalidData, match="Schema validation failed at 'tts_model'"):
        await _configure_subentry_flow(
            hass,
            result["flow_id"],
            {
                CONF_NAME: "Custom TTS",
                CONF_CHAT_MODEL: "tts-custom-deployment",
                CONF_TTS_MODEL: "",
                CONF_TTS_SPEED: 1.0,
            },
        )


async def test_tts_subentry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a TTS subentry when the parent entry is not loaded."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "tts"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def test_tts_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test reconfiguring the TTS subentry."""
    subentry = _get_subentry(mock_config_entry, "tts")
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    result = await _configure_subentry_flow(
        hass,
        subentry_flow["flow_id"],
        {
            CONF_CHAT_MODEL: "gpt-4o-mini-tts-preview-2025-12-15",
            CONF_TTS_MODEL: "gpt-4o-mini-tts",
            CONF_PROMPT: "Speak like a pirate",
            CONF_TTS_SPEED: 0.5,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data == {
        CONF_CHAT_MODEL: "gpt-4o-mini-tts-preview-2025-12-15",
        CONF_TTS_MODEL: "gpt-4o-mini-tts",
        CONF_PROMPT: "Speak like a pirate",
        CONF_TTS_SPEED: 0.5,
    }


async def test_tts_reconfigure_clears_instructions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test reconfiguring TTS clears omitted instructions."""
    subentry = _get_subentry(mock_config_entry, "tts")
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_PROMPT: "Speak like a pirate"},
    )
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    result = await _configure_subentry_flow(
        hass,
        subentry_flow["flow_id"],
        {
            CONF_CHAT_MODEL: "gpt-4o-mini-tts-preview-2025-12-15",
            CONF_TTS_MODEL: "gpt-4o-mini-tts",
            CONF_TTS_SPEED: 0.5,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data == {
        CONF_CHAT_MODEL: "gpt-4o-mini-tts-preview-2025-12-15",
        CONF_TTS_MODEL: "gpt-4o-mini-tts",
        CONF_PROMPT: "",
        CONF_TTS_SPEED: 0.5,
    }


@pytest.mark.parametrize(
    ("current_llm_apis", "suggested_llm_apis", "expected_options"),
    [
        pytest.param("assist", ["assist"], ["assist"], id="string-assist"),
        pytest.param(["assist"], ["assist"], ["assist"], id="list-assist"),
        pytest.param("non-existent", [], ["assist"], id="string-invalid"),
        pytest.param(["non-existent"], [], ["assist"], id="list-invalid"),
        pytest.param(
            ["assist", "non-existent"],
            ["assist"],
            ["assist"],
            id="mixed",
        ),
    ],
)
async def test_reconfigure_conversation_subentry_llm_api_schema(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    current_llm_apis: str | list[str],
    suggested_llm_apis: list[str],
    expected_options: list[str],
) -> None:
    """Test llm_hass_api suggestions are sanitized on reconfigure."""
    subentry = _get_subentry(mock_config_entry, "conversation")
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_PROMPT: "Speak like a pirate",
            CONF_LLM_HASS_API: current_llm_apis,
        },
    )
    await hass.async_block_till_done()

    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "init"

    schema = subentry_flow["data_schema"].schema
    key = next(key for key in schema if key == CONF_LLM_HASS_API)
    assert key.description
    assert key.description.get("suggested_value") == suggested_llm_apis
    field_schema = schema[key]
    assert field_schema.config
    assert [
        option["value"] for option in field_schema.config["options"]
    ] == expected_options
