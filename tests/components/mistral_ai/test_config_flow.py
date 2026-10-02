"""Tests for the Mistral AI config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.mistral_ai import DOMAIN
from homeassistant.components.mistral_ai.config_flow import (
    MistralAIConfigFlow,
    MistralConversationSubentryFlowHandler,
)
from homeassistant.components.mistral_ai.const import (
    CONF_CHAT_MODEL,
    CONF_LLM_HASS_API,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    DEFAULT_CONVERSATION_NAME,
    MISTRAL_MODELS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_CONVERSATION_OPTIONS,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


class _FakeError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"error {status_code}")


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a loaded config entry with a conversation subentry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mistral",
        data={CONF_API_KEY: "test-key"},
        version=2,
        state=config_entries.ConfigEntryState.LOADED,
        subentries_data=[
            {
                "subentry_type": "conversation",
                "data": RECOMMENDED_CONVERSATION_OPTIONS,
                "title": DEFAULT_CONVERSATION_NAME,
                "unique_id": None,
            },
        ],
    )
    entry.add_to_hass(hass)
    return entry


async def test_form(hass: HomeAssistant) -> None:
    """Test the initial form creates an entry with a conversation subentry."""
    hass.config.components.add(DOMAIN)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.mistral_ai.config_flow._validate_api_key",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "test-key"}
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {CONF_API_KEY: "test-key"}
    assert result2["subentries"] == [
        {
            "subentry_type": "conversation",
            "data": RECOMMENDED_CONVERSATION_OPTIONS,
            "title": DEFAULT_CONVERSATION_NAME,
            "unique_id": None,
        },
    ]
    assert result2["version"] == 2


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (_FakeError(401), "invalid_auth"),
        (_FakeError(403), "invalid_auth"),
        (_FakeError(500), "cannot_connect"),
        (Exception("boom"), "cannot_connect"),
    ],
)
async def test_form_invalid_auth(
    hass: HomeAssistant, error: Exception, message: str
) -> None:
    """Test validation errors are mapped to the right user-facing message."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.mistral_ai.config_flow._validate_api_key",
        side_effect=error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "test-key"}
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": message}


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test we abort when the same API key is configured twice."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-key"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with patch("homeassistant.components.mistral_ai.config_flow._validate_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "test-key"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_supported_subentry_types(hass: HomeAssistant) -> None:
    """Test the supported subentry types match the conversation service."""
    types = MistralAIConfigFlow.async_get_supported_subentry_types(None)
    assert set(types) == {"conversation"}
    assert types["conversation"] is MistralConversationSubentryFlowHandler


async def test_creating_conversation_subentry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test creating a conversation subentry with recommended settings."""
    with patch(
        "homeassistant.components.mistral_ai.config_flow._async_fetch_models",
        new_callable=AsyncMock,
        return_value=MISTRAL_MODELS,
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch(
        "homeassistant.components.mistral_ai.config_flow._async_fetch_models",
        new_callable=AsyncMock,
        return_value=MISTRAL_MODELS,
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"name": "My Custom Agent", CONF_RECOMMENDED: True},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "My Custom Agent"


async def test_subentry_not_loaded(hass: HomeAssistant) -> None:
    """Test aborting a subentry flow when the entry is not loaded."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-key"},
        version=2,
        subentries_data=[
            {
                "subentry_type": "conversation",
                "data": RECOMMENDED_CONVERSATION_OPTIONS,
                "title": DEFAULT_CONVERSATION_NAME,
                "unique_id": None,
            },
        ],
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def test_subentry_recommended(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring a subentry with recommended settings."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "init"

    with patch(
        "homeassistant.components.mistral_ai.config_flow._async_fetch_models",
        new_callable=AsyncMock,
        return_value=MISTRAL_MODELS,
    ):
        options = await hass.config_entries.subentries.async_configure(
            subentry_flow["flow_id"],
            {
                CONF_PROMPT: "Speak like a pirate",
                CONF_RECOMMENDED: True,
                CONF_LLM_HASS_API: ["assist"],
            },
        )
        await hass.async_block_till_done()

    assert options["type"] is FlowResultType.ABORT
    assert options["reason"] == "reconfigure_successful"
    assert subentry.data[CONF_PROMPT] == "Speak like a pirate"


async def test_subentry_advanced(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the advanced settings step of a conversation subentry."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    with patch(
        "homeassistant.components.mistral_ai.config_flow._async_fetch_models",
        new_callable=AsyncMock,
        return_value=MISTRAL_MODELS,
    ):
        subentry_flow = await hass.config_entries.subentries.async_configure(
            subentry_flow["flow_id"],
            {
                CONF_RECOMMENDED: False,
                CONF_PROMPT: "Speak like a pirate",
                CONF_LLM_HASS_API: ["assist"],
                CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
            },
        )
        await hass.async_block_till_done()

    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "advanced"

    subentry_flow = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            "max_tokens": 100,
            "temperature": 0.5,
            "top_p": 0.9,
        },
    )
    await hass.async_block_till_done()

    assert subentry_flow["type"] is FlowResultType.ABORT
    assert subentry_flow["reason"] == "reconfigure_successful"
    assert subentry.data["max_tokens"] == 100
    assert subentry.data["temperature"] == 0.5
    assert subentry.data["top_p"] == 0.9
