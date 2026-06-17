"""Tests for the OpenRouter integration."""

from unittest.mock import AsyncMock, patch

from python_open_router import OpenRouterError

from homeassistant.components.open_router.const import (
    CONF_OUTPUT_MODALITIES,
    CONF_PROMPT,
    CONF_WEB_SEARCH,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from tests.common import MockConfigEntry


async def test_migrate_entry_from_v1_1_to_v1_3(
    hass: HomeAssistant,
    mock_open_router_client_setup: AsyncMock,
) -> None:
    """Test migration from version 1.1 to 1.3."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
        },
        version=1,
        minor_version=1,
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_MODEL: "openai/gpt-3.5-turbo",
                    CONF_PROMPT: "You are a helpful assistant.",
                    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
                },
                subentry_id="conversation_subentry",
                subentry_type="conversation",
                title="GPT-3.5 Turbo",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    CONF_MODEL: "openai/gpt-4",
                },
                subentry_id="ai_task_subentry",
                subentry_type="ai_task_data",
                title="GPT-4",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    CONF_MODEL: "google/gemini-2.5-flash-image",
                },
                subentry_id="ai_task_image_subentry",
                subentry_type="ai_task_data",
                title="Gemini 2.5 Flash Image",
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.open_router.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 1
    assert entry.minor_version == 3

    conversation_subentry = entry.subentries["conversation_subentry"]
    assert conversation_subentry.data[CONF_MODEL] == "openai/gpt-3.5-turbo"
    assert conversation_subentry.data[CONF_PROMPT] == "You are a helpful assistant."
    assert conversation_subentry.data[CONF_LLM_HASS_API] == [llm.LLM_API_ASSIST]
    assert conversation_subentry.data[CONF_WEB_SEARCH] is False
    # Conversation subentries are not given output modalities
    assert CONF_OUTPUT_MODALITIES not in conversation_subentry.data

    ai_task_subentry = entry.subentries["ai_task_subentry"]
    assert ai_task_subentry.data[CONF_MODEL] == "openai/gpt-4"
    assert ai_task_subentry.data[CONF_WEB_SEARCH] is False
    assert ai_task_subentry.data[CONF_OUTPUT_MODALITIES] == ["text"]

    image_subentry = entry.subentries["ai_task_image_subentry"]
    assert image_subentry.data[CONF_MODEL] == "google/gemini-2.5-flash-image"
    assert image_subentry.data[CONF_OUTPUT_MODALITIES] == ["text", "image"]


async def test_migrate_entry_v1_2_to_v1_3_unknown_model(
    hass: HomeAssistant,
    mock_open_router_client_setup: AsyncMock,
) -> None:
    """Test migration backfills empty modalities for an unknown model."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
        },
        version=1,
        minor_version=2,
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_MODEL: "some/removed-model",
                    CONF_WEB_SEARCH: False,
                },
                subentry_id="ai_task_subentry",
                subentry_type="ai_task_data",
                title="Removed model",
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.open_router.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 1
    assert entry.minor_version == 3
    assert entry.subentries["ai_task_subentry"].data[CONF_OUTPUT_MODALITIES] == []


async def test_migrate_entry_v1_2_to_v1_3_api_error(
    hass: HomeAssistant,
    mock_open_router_client_setup: AsyncMock,
) -> None:
    """Test migration retries when the model list cannot be fetched."""
    mock_open_router_client_setup.get_models.side_effect = OpenRouterError("boom")

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
        },
        version=1,
        minor_version=2,
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_MODEL: "openai/gpt-4",
                    CONF_WEB_SEARCH: False,
                },
                subentry_id="ai_task_subentry",
                subentry_type="ai_task_data",
                title="GPT-4",
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.minor_version == 2
    assert CONF_OUTPUT_MODALITIES not in entry.subentries["ai_task_subentry"].data


async def test_migrate_entry_from_future_version_fails(
    hass: HomeAssistant,
) -> None:
    """Test migration fails for future versions."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
        },
        version=100,
        minor_version=99,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 100
    assert entry.minor_version == 99
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
