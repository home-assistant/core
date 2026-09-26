"""Test the LiteLLM config flow."""

from unittest.mock import AsyncMock, patch

import httpx
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    PermissionDeniedError,
)
import pytest

from homeassistant.components.litellm.config_flow import (
    CannotConnect,
    InvalidAuth,
    _get_models,
    _normalize_url,
)
from homeassistant.components.litellm.const import (
    CONF_PROMPT,
    CONF_STT_CUSTOM_PROMPT_KEYWORDS,
    CONF_STT_KEYWORDS,
    CONF_STT_PROMPT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import llm

from . import get_subentry_id, setup_integration
from .conftest import MODELS, TEST_URL

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("url", "normalized"),
    [
        (
            "http://localhost:4000",
            "http://localhost:4000/v1",
        ),
        (
            "http://localhost:4000/api/",
            "http://localhost:4000/api/v1",
        ),
        (
            "http://localhost:4000/api/v1",
            "http://localhost:4000/api/v1",
        ),
    ],
)
def test_normalize_url(url: str, normalized: str) -> None:
    """Test LiteLLM API URL normalization."""
    assert _normalize_url(url) == normalized


async def test_get_models_requests_model_list(hass: HomeAssistant) -> None:
    """Test the OpenAI client requests the model list with bearer auth."""
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {
                        "id": model,
                        "object": "model",
                        "created": 0,
                        "owned_by": "litellm",
                    }
                    for model in MODELS
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with patch(
            "homeassistant.components.litellm.config_flow.get_async_client",
            return_value=client,
        ):
            models = await _get_models(hass, TEST_URL, "bla")

    assert models == MODELS
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert str(requests[0].url) == "http://localhost:4000/v1/models"
    assert requests[0].headers["Authorization"] == "Bearer bla"


CONVERSATION_MODEL_OPTIONS = [
    {"value": "gpt-4o", "label": "gpt-4o"},
    {"value": "gpt-4o-transcribe", "label": "gpt-4o-transcribe"},
]


@pytest.mark.usefixtures("mock_setup_entry", "mock_models")
@pytest.mark.parametrize(
    "url_input",
    ["http://localhost:4000", "http://localhost:4000/", TEST_URL, f"{TEST_URL}/"],
)
async def test_full_flow(hass: HomeAssistant, url_input: str) -> None:
    """Test the full config flow normalizes the URL and stores the key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: url_input, CONF_API_KEY: "bla"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "localhost"
    assert result["data"] == {CONF_URL: TEST_URL, CONF_API_KEY: "bla"}


@pytest.mark.usefixtures("mock_setup_entry", "mock_models")
async def test_full_flow_without_api_key(hass: HomeAssistant) -> None:
    """Test the config flow works without an API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "http://localhost:4000"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_URL: TEST_URL}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (InvalidAuth, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_errors(
    hass: HomeAssistant,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle errors and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.litellm.config_flow._get_models",
        new_callable=AsyncMock,
    ) as mock_get_models:
        mock_get_models.side_effect = exception

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: "http://localhost:4000", CONF_API_KEY: "bla"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error}

        mock_get_models.side_effect = None
        mock_get_models.return_value = MODELS

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: "http://localhost:4000", CONF_API_KEY: "bla"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


def _status_error(
    error: type[AuthenticationError | PermissionDeniedError], status_code: int
) -> AuthenticationError | PermissionDeniedError:
    """Build an OpenAI status error backed by a real httpx response."""
    return error(
        response=httpx.Response(
            status_code=status_code, request=httpx.Request("GET", TEST_URL)
        ),
        body=None,
        message="error",
    )


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (_status_error(AuthenticationError, 401), "invalid_auth"),
        (_status_error(PermissionDeniedError, 403), "invalid_auth"),
        (APIConnectionError(request=httpx.Request("GET", TEST_URL)), "cannot_connect"),
        (APITimeoutError(request=httpx.Request("GET", TEST_URL)), "cannot_connect"),
    ],
)
async def test_user_step_proxy_errors(
    hass: HomeAssistant,
    side_effect: Exception,
    error: str,
) -> None:
    """Test the user step surfaces errors raised by the OpenAI client."""
    with patch(
        "homeassistant.components.litellm.config_flow.AsyncOpenAI"
    ) as mock_client:
        mock_client.return_value.with_options.return_value.models.list.side_effect = (
            side_effect
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: "http://localhost:4000", CONF_API_KEY: "bla"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting the flow if an entry with the same URL already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "http://localhost:4000", CONF_API_KEY: "other"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (InvalidAuth(), "invalid_auth"),
        (CannotConnect(), "cannot_connect"),
        (Exception("unexpected"), "unknown"),
    ],
)
async def test_stt_subentry_exceptions(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    reason: str,
) -> None:
    """Test STT subentry flow aborts when models cannot be fetched."""
    await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.litellm.config_flow._get_models",
        new_callable=AsyncMock,
        side_effect=exception,
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "stt"),
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_create_stt_subentry(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating an STT subentry."""
    await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.litellm.config_flow._get_models",
        new_callable=AsyncMock,
        return_value=["gpt-4o-transcribe", "gpt-4o", "gpt-realtime", "custom-stt"],
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "stt"),
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert schema["model"].config["options"] == [
        {"value": "gpt-4o-transcribe", "label": "gpt-4o-transcribe"},
        {"value": "gpt-4o", "label": "gpt-4o"},
        {"value": "gpt-realtime", "label": "gpt-realtime"},
        {"value": "custom-stt", "label": "custom-stt"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "gpt-4o-transcribe", CONF_STT_CUSTOM_PROMPT_KEYWORDS: False},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "gpt-4o-transcribe"
    assert result["data"] == {
        CONF_MODEL: "gpt-4o-transcribe",
        CONF_STT_CUSTOM_PROMPT_KEYWORDS: False,
    }

    subentry_id = get_subentry_id(mock_config_entry, "stt")
    with patch(
        "homeassistant.components.litellm.config_flow._get_models",
        new_callable=AsyncMock,
        return_value=["gpt-4o-transcribe"],
    ):
        result = await mock_config_entry.start_subentry_reconfigure_flow(
            hass, subentry_id
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_MODEL: "gpt-4o-transcribe", CONF_STT_CUSTOM_PROMPT_KEYWORDS: False},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def _create_stt_with_hints(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> str:
    """Create an STT subentry with both optional hints enabled."""
    await setup_integration(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "stt"), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "gpt-4o-transcribe", CONF_STT_CUSTOM_PROMPT_KEYWORDS: True},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "gpt-4o-transcribe",
            CONF_STT_CUSTOM_PROMPT_KEYWORDS: True,
            CONF_STT_PROMPT: "Old prompt",
            CONF_STT_KEYWORDS: "Old, keywords",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    return get_subentry_id(mock_config_entry, "stt")


@pytest.mark.usefixtures("mock_openai_client", "mock_get_models")
@pytest.mark.parametrize(
    ("hints", "expected_hints"),
    [
        pytest.param({}, {}, id="clear-both-omitted"),
        pytest.param(
            {CONF_STT_KEYWORDS: "Old, keywords"},
            {CONF_STT_KEYWORDS: "Old, keywords"},
            id="clear-prompt",
        ),
        pytest.param(
            {CONF_STT_PROMPT: "Old prompt"},
            {CONF_STT_PROMPT: "Old prompt"},
            id="clear-keywords",
        ),
        pytest.param(
            {CONF_STT_PROMPT: "", CONF_STT_KEYWORDS: ""},
            {},
            id="clear-both-empty",
        ),
        pytest.param(
            {CONF_STT_PROMPT: "New prompt", CONF_STT_KEYWORDS: "New, keywords"},
            {CONF_STT_PROMPT: "New prompt", CONF_STT_KEYWORDS: "New, keywords"},
            id="edit-both",
        ),
    ],
)
async def test_reconfigure_stt_hints(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hints: dict[str, str],
    expected_hints: dict[str, str],
) -> None:
    """Test saved STT hints reflect the submitted form fields."""
    subentry_id = await _create_stt_with_hints(hass, mock_config_entry)

    result = await mock_config_entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "gpt-4o-transcribe",
            CONF_STT_CUSTOM_PROMPT_KEYWORDS: True,
            **hints,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.subentries[subentry_id].data == {
        CONF_MODEL: "gpt-4o-transcribe",
        CONF_STT_CUSTOM_PROMPT_KEYWORDS: True,
        **expected_hints,
    }


@pytest.mark.usefixtures("mock_openai_client", "mock_get_models")
async def test_reconfigure_stt_disable_hints(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test disabling hints clears both saved STT fields."""
    subentry_id = await _create_stt_with_hints(hass, mock_config_entry)

    result = await mock_config_entry.start_subentry_reconfigure_flow(hass, subentry_id)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "gpt-4o-transcribe", CONF_STT_CUSTOM_PROMPT_KEYWORDS: False},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "gpt-4o-transcribe", CONF_STT_CUSTOM_PROMPT_KEYWORDS: False},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.subentries[subentry_id].data == {
        CONF_MODEL: "gpt-4o-transcribe",
        CONF_STT_CUSTOM_PROMPT_KEYWORDS: False,
    }


@pytest.mark.usefixtures("mock_get_models")
async def test_create_conversation_agent(
    hass: HomeAssistant,
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
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert schema["model"].config["options"] == CONVERSATION_MODEL_OPTIONS
    key = next(k for k in schema if k == CONF_LLM_HASS_API)
    assert key.default() == [llm.LLM_API_ASSIST]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "gpt-4o",
            CONF_PROMPT: "you are an assistant",
            CONF_LLM_HASS_API: ["assist"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "gpt-4o"
    assert result["data"] == {
        CONF_MODEL: "gpt-4o",
        CONF_PROMPT: "you are an assistant",
        CONF_LLM_HASS_API: ["assist"],
    }


@pytest.mark.usefixtures("mock_get_models")
async def test_create_conversation_agent_no_control(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation agent without control over the LLM API."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "gpt-4o",
            CONF_PROMPT: "you are an assistant",
            CONF_LLM_HASS_API: [],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_MODEL: "gpt-4o",
        CONF_PROMPT: "you are an assistant",
        CONF_LLM_HASS_API: [],
    }


async def test_conversation_agent_model_options(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test every model from the proxy is available in the dropdown."""
    await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.litellm.config_flow._get_models",
        new_callable=AsyncMock,
        return_value=["gpt-4o", "gpt-4o-transcribe", "legacy-completion", "realtime"],
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"].schema["model"].config["options"] == [
        {"value": "gpt-4o", "label": "gpt-4o"},
        {"value": "gpt-4o-transcribe", "label": "gpt-4o-transcribe"},
        {"value": "legacy-completion", "label": "legacy-completion"},
        {"value": "realtime", "label": "realtime"},
    ]


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (InvalidAuth(), "invalid_auth"),
        (CannotConnect(), "cannot_connect"),
        (Exception("unexpected"), "unknown"),
    ],
)
async def test_conversation_subentry_exceptions(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    reason: str,
) -> None:
    """Test subentry flow aborts on errors fetching models."""
    await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.litellm.config_flow._get_models",
        new_callable=AsyncMock,
        side_effect=exception,
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("mock_get_models")
async def test_reconfigure_conversation_agent(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring a conversation agent."""
    await setup_integration(hass, mock_config_entry)

    subentry_id = get_subentry_id(mock_config_entry, "conversation")

    result = await mock_config_entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "gpt-4o",
            CONF_PROMPT: "updated prompt",
            CONF_LLM_HASS_API: ["assist"],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    subentry = mock_config_entry.subentries[subentry_id]
    assert subentry.title == "gpt-4o"
    assert subentry.data[CONF_MODEL] == "gpt-4o"
    assert subentry.data[CONF_PROMPT] == "updated prompt"
    assert subentry.data[CONF_LLM_HASS_API] == ["assist"]


@pytest.mark.usefixtures("mock_get_models")
async def test_reconfigure_conversation_agent_disable_llm_api(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unchecking all LLM APIs is remembered when reopening the form."""
    await setup_integration(hass, mock_config_entry)

    subentry_id = get_subentry_id(mock_config_entry, "conversation")

    result = await mock_config_entry.start_subentry_reconfigure_flow(hass, subentry_id)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "gpt-4o",
            CONF_PROMPT: "updated prompt",
            CONF_LLM_HASS_API: [],
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.subentries[subentry_id].data[CONF_LLM_HASS_API] == []

    result = await mock_config_entry.start_subentry_reconfigure_flow(hass, subentry_id)
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == CONF_LLM_HASS_API)
    assert key.default() == []


@pytest.mark.parametrize("subentry_type", ["conversation", "stt"])
async def test_reconfigure_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    subentry_type: str,
) -> None:
    """Test reconfiguring aborts when the main entry is not loaded."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, subentry_type),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


@pytest.mark.parametrize(
    ("current_llm_apis", "suggested_llm_apis", "expected_options"),
    [
        (["assist"], ["assist"], ["assist"]),
        (["non-existent"], [], ["assist"]),
        (["assist", "non-existent"], ["assist"], ["assist"]),
    ],
)
@pytest.mark.usefixtures("mock_get_models")
async def test_reconfigure_conversation_subentry_llm_api_schema(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    current_llm_apis: list[str],
    suggested_llm_apis: list[str],
    expected_options: list[str],
) -> None:
    """Test llm_hass_api field values when reconfiguring a conversation subentry."""
    await setup_integration(hass, mock_config_entry)

    subentry_id = get_subentry_id(mock_config_entry, "conversation")
    subentry = mock_config_entry.subentries[subentry_id]
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_LLM_HASS_API: current_llm_apis},
    )
    await hass.async_block_till_done()

    result = await mock_config_entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    schema = result["data_schema"].schema
    key = next(k for k in schema if k == CONF_LLM_HASS_API)
    assert key.default() == suggested_llm_apis

    field_schema = schema[key]
    assert field_schema.config
    assert [
        opt["value"] for opt in field_schema.config.get("options")
    ] == expected_options
