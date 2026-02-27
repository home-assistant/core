"""Tests for the OpenRouter integration."""

from unittest.mock import patch

from homeassistant.components.open_router.const import (
    CONF_PROMPT,
    CONF_WEB_SEARCH,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from tests.common import MockConfigEntry


async def test_migrate_entry_from_v1_0_to_v1_1(
    hass: HomeAssistant,
) -> None:
    """Test migration from version 1.0 to 1.1."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
        },
        version=1,
        minor_version=0,
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
    assert entry.minor_version == 1

    conversation_subentry = entry.subentries["conversation_subentry"]
    assert conversation_subentry.data[CONF_MODEL] == "openai/gpt-3.5-turbo"
    assert conversation_subentry.data[CONF_PROMPT] == "You are a helpful assistant."
    assert conversation_subentry.data[CONF_LLM_HASS_API] == [llm.LLM_API_ASSIST]
    assert conversation_subentry.data[CONF_WEB_SEARCH] is False

    ai_task_subentry = entry.subentries["ai_task_subentry"]
    assert ai_task_subentry.data[CONF_MODEL] == "openai/gpt-4"
    assert ai_task_subentry.data[CONF_WEB_SEARCH] is False


async def test_migrate_entry_already_migrated(
    hass: HomeAssistant,
) -> None:
    """Test migration is skipped when already on version 1.1."""
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
                    CONF_WEB_SEARCH: True,
                },
                subentry_id="conversation_subentry",
                subentry_type="conversation",
                title="GPT-3.5 Turbo",
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
    assert entry.minor_version == 1

    conversation_subentry = entry.subentries["conversation_subentry"]
    assert conversation_subentry.data[CONF_MODEL] == "openai/gpt-3.5-turbo"
    assert conversation_subentry.data[CONF_WEB_SEARCH] is True


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
