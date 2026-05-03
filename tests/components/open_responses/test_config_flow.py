"""Test the Open Responses config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.open_responses.client import (
    OpenResponsesConnectionError,
    OpenResponsesInvalidModelError,
)
from homeassistant.components.open_responses.const import (
    CONF_BASE_URL,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CONVERSATION_OPTIONS,
)
from homeassistant.const import CONF_API_KEY, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.open_responses.config_flow.OpenResponsesClient"
        ) as mock_open_responses_client,
        patch(
            "homeassistant.components.open_responses.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        mock_open_responses_client.return_value.create_response = AsyncMock()
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
        CONF_MODEL: "open-responses-model",
    }
    expected_ai_task_options = {
        **RECOMMENDED_AI_TASK_OPTIONS,
        CONF_MODEL: "open-responses-model",
    }
    assert result2["subentries"] == [
        {
            "subentry_type": "conversation",
            "data": expected_conversation_options,
            "title": DEFAULT_CONVERSATION_NAME,
            "unique_id": None,
        },
        {
            "subentry_type": "ai_task_data",
            "data": expected_ai_task_options,
            "title": DEFAULT_AI_TASK_NAME,
            "unique_id": None,
        },
    ]
    assert result2["version"] == 1
    mock_open_responses_client.return_value.create_response.assert_awaited_once_with(
        model="open-responses-model",
        input=[{"type": "message", "role": "user", "content": "ping"}],
        max_output_tokens=16,
        store=False,
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
        "homeassistant.components.open_responses.config_flow.OpenResponsesClient"
    ) as mock_open_responses_client:
        mock_open_responses_client.return_value.create_response = AsyncMock(
            side_effect=OpenResponsesConnectionError("boom")
        )
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
        "homeassistant.components.open_responses.config_flow.OpenResponsesClient"
    ) as mock_open_responses_client:
        mock_open_responses_client.return_value.create_response = AsyncMock(
            side_effect=OpenResponsesInvalidModelError("boom")
        )
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


async def test_reauth_updates_default_subentry_models(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth model changes are propagated to generated subentries."""
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.open_responses.config_flow.OpenResponsesClient"
        ) as mock_open_responses_client,
        patch(
            "homeassistant.components.open_responses.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.open_responses.async_unload_entry",
            return_value=True,
        ),
    ):
        mock_open_responses_client.return_value.create_response = AsyncMock()
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
    assert {
        subentry.data[CONF_MODEL] for subentry in mock_config_entry.subentries.values()
    } == {"new-open-responses-model"}


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

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "My Custom Agent", **RECOMMENDED_CONVERSATION_OPTIONS},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "My Custom Agent"
