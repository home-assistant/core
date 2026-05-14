"""Test the Open Responses config flow."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import openai
import pytest

from homeassistant import config_entries
from homeassistant.components.open_responses.config_flow import VALIDATION_TIMEOUT
from homeassistant.components.open_responses.const import (
    CONF_BASE_URL,
    CONF_GENERATED_DEFAULT_SUBENTRY,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    RECOMMENDED_CONVERSATION_OPTIONS,
)
from homeassistant.const import CONF_API_KEY, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from tests.common import MockConfigEntry


def _api_request() -> httpx.Request:
    """Return a mock Open Responses request."""
    return httpx.Request("POST", "https://example.local/v1/responses")


def _api_connection_error() -> openai.APIConnectionError:
    """Return a mock OpenAI SDK connection error."""
    return openai.APIConnectionError(request=_api_request())


def _bad_request_error(error: dict[str, Any]) -> openai.BadRequestError:
    """Return a mock OpenAI SDK bad request error."""
    return openai.BadRequestError(
        message="bad request",
        response=httpx.Response(400, json={"error": error}, request=_api_request()),
        body={"error": error},
    )


def _rate_limit_error() -> openai.RateLimitError:
    """Return a mock OpenAI SDK rate limit error."""
    return openai.RateLimitError(
        message="rate limited",
        response=httpx.Response(429, request=_api_request()),
        body=None,
    )


async def _mock_stream_response(**_: Any) -> AsyncGenerator[dict[str, Any]]:
    """Mock a valid streaming validation response."""
    yield {"type": "response.completed", "response": {}}


def _mock_successful_validation(mock_create: AsyncMock) -> None:
    """Mock non-streaming and streaming validation calls."""

    async def create(**params: Any) -> object:
        if params.get("stream"):
            return _mock_stream_response()
        return object()

    mock_create.side_effect = create


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "openai.resources.responses.AsyncResponses.create",
            new_callable=AsyncMock,
        ) as mock_create,
        patch(
            "homeassistant.components.open_responses.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        _mock_successful_validation(mock_create)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "bla",
                CONF_BASE_URL: "https://example.local/v1",
                CONF_MODEL: "open-responses-model",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_API_KEY: "bla",
        CONF_BASE_URL: "https://example.local/v1",
        CONF_MODEL: "open-responses-model",
    }
    assert result2["options"] == {}
    expected_conversation_options = {
        **RECOMMENDED_CONVERSATION_OPTIONS,
        CONF_GENERATED_DEFAULT_SUBENTRY: True,
        CONF_MODEL: "open-responses-model",
    }
    assert result2["subentries"] == [
        {
            "subentry_type": "conversation",
            "data": expected_conversation_options,
            "title": DEFAULT_CONVERSATION_NAME,
            "unique_id": None,
        },
    ]
    assert result2["version"] == 1
    mock_create.assert_any_await(
        model="open-responses-model",
        input=[{"type": "message", "role": "user", "content": "ping"}],
        max_output_tokens=16,
        store=False,
        timeout=VALIDATION_TIMEOUT,
    )
    mock_create.assert_any_await(
        model="open-responses-model",
        input=[{"type": "message", "role": "user", "content": "ping"}],
        max_output_tokens=16,
        store=False,
        stream=True,
        timeout=VALIDATION_TIMEOUT,
    )
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test we abort on duplicate config entry."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
            CONF_BASE_URL: "https://example.local/v1",
            CONF_MODEL: "open-responses-model",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "bla",
            CONF_BASE_URL: "https://example.local/v1",
            CONF_MODEL: "open-responses-model",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_duplicate_entry_normalizes_base_url(hass: HomeAssistant) -> None:
    """Test equivalent base URLs are treated as duplicate entries."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
            CONF_BASE_URL: "https://example.local/v1",
            CONF_MODEL: "open-responses-model",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "bla",
            CONF_BASE_URL: "https://example.local/v1/",
            CONF_MODEL: "open-responses-model",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_base_url(hass: HomeAssistant) -> None:
    """Test the base URL is validated by the form schema."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with pytest.raises(InvalidData) as err:
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "bla",
                CONF_BASE_URL: "not a url",
                CONF_MODEL: "open-responses-model",
            },
        )

    assert err.value.schema_errors == {CONF_BASE_URL: "invalid url"}


async def test_form_validates_endpoint(hass: HomeAssistant) -> None:
    """Test the endpoint is validated before creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new_callable=AsyncMock,
        side_effect=_api_connection_error(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "bla",
                CONF_BASE_URL: "https://example.local/v1",
                CONF_MODEL: "open-responses-model",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_handles_invalid_model(hass: HomeAssistant) -> None:
    """Test model validation errors are shown on the model field."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new_callable=AsyncMock,
        side_effect=_bad_request_error({"message": "Unknown model", "param": "model"}),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "bla",
                CONF_BASE_URL: "https://example.local/v1",
                CONF_MODEL: "missing-model",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_MODEL: "invalid_model"}


async def test_form_handles_rate_limit(hass: HomeAssistant) -> None:
    """Test rate limit errors are shown on the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new_callable=AsyncMock,
        side_effect=_rate_limit_error(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "bla",
                CONF_BASE_URL: "https://example.local/v1",
                CONF_MODEL: "open-responses-model",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "rate_limited"}


async def test_form_validates_stream_endpoint(hass: HomeAssistant) -> None:
    """Test the streaming endpoint is validated before creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    async def failing_stream_response(
        **params: Any,
    ) -> AsyncGenerator[dict[str, Any]]:
        if not params:
            yield {}
        raise _api_connection_error()

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.side_effect = [object(), failing_stream_response()]
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "bla",
                CONF_BASE_URL: "https://example.local/v1",
                CONF_MODEL: "open-responses-model",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_rejects_stream_error_events(hass: HomeAssistant) -> None:
    """Test streaming error events are rejected before creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    async def failing_stream_response() -> AsyncGenerator[dict[str, Any]]:
        yield {
            "type": "response.failed",
            "response": {"error": {"message": "stream failed"}},
        }

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.side_effect = [object(), failing_stream_response()]
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "bla",
                CONF_BASE_URL: "https://example.local/v1",
                CONF_MODEL: "open-responses-model",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_reauth_updates_default_subentry_models(
    hass: HomeAssistant,
) -> None:
    """Test reauth model changes are propagated to generated subentries."""
    mock_config_entry = MockConfigEntry(
        title="Open Responses",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
            CONF_BASE_URL: "https://example.local/v1",
            CONF_MODEL: "open-responses-model",
        },
        version=1,
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={
                    **RECOMMENDED_CONVERSATION_OPTIONS,
                    CONF_GENERATED_DEFAULT_SUBENTRY: True,
                    CONF_MODEL: "open-responses-model",
                },
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
            config_entries.ConfigSubentryData(
                data={
                    **RECOMMENDED_CONVERSATION_OPTIONS,
                    CONF_MODEL: "open-responses-model",
                },
                subentry_type="conversation",
                title="My Custom Agent",
                unique_id=None,
            ),
            config_entries.ConfigSubentryData(
                data={
                    **RECOMMENDED_CONVERSATION_OPTIONS,
                    CONF_MODEL: "open-responses-model",
                },
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
        ],
    )
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "openai.resources.responses.AsyncResponses.create",
            new_callable=AsyncMock,
        ) as mock_create,
        patch(
            "homeassistant.components.open_responses.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.open_responses.async_unload_entry",
            return_value=True,
        ),
    ):
        _mock_successful_validation(mock_create)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "bla",
                CONF_BASE_URL: "https://example.local/v1",
                CONF_MODEL: "new-open-responses-model",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_MODEL] == "new-open-responses-model"
    default_title_models = [
        subentry.data[CONF_MODEL]
        for subentry in mock_config_entry.subentries.values()
        if subentry.title == DEFAULT_CONVERSATION_NAME
    ]
    assert sorted(default_title_models) == [
        "new-open-responses-model",
        "open-responses-model",
    ]
    assert {
        subentry.title: subentry.data[CONF_MODEL]
        for subentry in mock_config_entry.subentries.values()
        if subentry.title != DEFAULT_CONVERSATION_NAME
    } == {
        "My Custom Agent": "open-responses-model",
    }


async def test_creating_conversation_subentry(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation subentry."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert not result["errors"]

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new_callable=AsyncMock,
    ) as mock_create:
        _mock_successful_validation(mock_create)
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_NAME: "My Custom Agent", **RECOMMENDED_CONVERSATION_OPTIONS},
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "My Custom Agent"
    mock_create.assert_any_await(
        model=mock_config_entry.data[CONF_MODEL],
        input=[{"type": "message", "role": "user", "content": "ping"}],
        max_output_tokens=16,
        store=False,
        timeout=VALIDATION_TIMEOUT,
    )


async def test_creating_subentry_validates_model(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test subentry creation validates the selected model."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new_callable=AsyncMock,
        side_effect=_bad_request_error({"message": "Unknown model", "param": "model"}),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "My Custom Agent",
                **RECOMMENDED_CONVERSATION_OPTIONS,
                CONF_MODEL: "missing-model",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "init"
    assert result2["errors"] == {CONF_MODEL: "invalid_model"}


async def test_creating_subentry_handles_rate_limit(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test subentry creation handles rate limit errors."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new_callable=AsyncMock,
        side_effect=_rate_limit_error(),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "My Custom Agent",
                **RECOMMENDED_CONVERSATION_OPTIONS,
                CONF_MODEL: "rate-limited-model",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "init"
    assert result2["errors"] == {"base": "rate_limited"}


async def test_reconfiguring_default_subentry_preserves_marker(
    hass: HomeAssistant,
    mock_init_component: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring generated defaults keeps them marked as generated."""
    subentry = mock_config_entry.get_subentries_of_type("conversation")[0]

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "subentry_id": subentry.subentry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new_callable=AsyncMock,
    ) as mock_create:
        _mock_successful_validation(mock_create)
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                **RECOMMENDED_CONVERSATION_OPTIONS,
                CONF_MODEL: "new-open-responses-model",
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert subentry.data[CONF_GENERATED_DEFAULT_SUBENTRY] is True
    assert subentry.data[CONF_MODEL] == "new-open-responses-model"
