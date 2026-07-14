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


async def test_migrate_entry_from_v1_1_to_v1_3(
    hass: HomeAssistant,
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
    assert conversation_subentry.data[CONF_WEB_SEARCH] == "off"

    ai_task_subentry = entry.subentries["ai_task_subentry"]
    assert ai_task_subentry.data[CONF_MODEL] == "openai/gpt-4"
    assert ai_task_subentry.data[CONF_WEB_SEARCH] == "off"


async def test_migrate_entry_from_v1_2_to_v1_3(
    hass: HomeAssistant,
) -> None:
    """Test migration from version 1.2 to 1.3."""
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
                    CONF_MODEL: "openai/gpt-3.5-turbo",
                    CONF_PROMPT: "You are a helpful assistant.",
                    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
                    CONF_WEB_SEARCH: True,
                },
                subentry_id="online_subentry",
                subentry_type="conversation",
                title="GPT-3.5 Turbo",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    CONF_MODEL: "openai/gpt-3.5-turbo",
                    CONF_PROMPT: "You are a helpful assistant.",
                    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
                    CONF_WEB_SEARCH: False,
                },
                subentry_id="offline_subentry",
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
    assert entry.minor_version == 3

    online_subentry = entry.subentries["online_subentry"]
    assert online_subentry.data[CONF_MODEL] == "openai/gpt-3.5-turbo"
    assert online_subentry.data[CONF_PROMPT] == "You are a helpful assistant."
    assert online_subentry.data[CONF_LLM_HASS_API] == [llm.LLM_API_ASSIST]
    assert online_subentry.data[CONF_WEB_SEARCH] == "plugin"

    offline_subentry = entry.subentries["offline_subentry"]
    assert offline_subentry.data[CONF_MODEL] == "openai/gpt-3.5-turbo"
    assert offline_subentry.data[CONF_PROMPT] == "You are a helpful assistant."
    assert offline_subentry.data[CONF_LLM_HASS_API] == [llm.LLM_API_ASSIST]
    assert offline_subentry.data[CONF_WEB_SEARCH] == "off"


async def test_migrate_entry_already_migrated(
    hass: HomeAssistant,
) -> None:
    """Test migration is skipped when already on version 1.3."""
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
                    CONF_WEB_SEARCH: "plugin",
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
    assert entry.minor_version == 3

    conversation_subentry = entry.subentries["conversation_subentry"]
    assert conversation_subentry.data[CONF_MODEL] == "openai/gpt-3.5-turbo"
    assert conversation_subentry.data[CONF_WEB_SEARCH] == "plugin"


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
