"""Conversation test helpers."""

from collections.abc import AsyncGenerator
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.shopping_list import intent as sl_intent
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MockAgent

from tests.common import MockConfigEntry


@pytest.fixture
def mock_agent_support_all(hass: HomeAssistant) -> MockAgent:
    """Mock agent that supports all languages."""
    entry = MockConfigEntry(entry_id="mock-entry-support-all")
    entry.add_to_hass(hass)
    agent = MockAgent(entry.entry_id, MATCH_ALL)
    conversation.async_set_agent(hass, entry, agent)
    return agent


@pytest.fixture(autouse=True)
def mock_shopping_list_io():
    """Stub out the persistence."""
    with (
        patch("homeassistant.components.shopping_list.ShoppingData.save"),
        patch("homeassistant.components.shopping_list.ShoppingData.async_load"),
    ):
        yield


@pytest.fixture
async def sl_setup(hass: HomeAssistant):
    """Set up the shopping list."""

    entry = MockConfigEntry(domain="shopping_list")
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    await sl_intent.async_setup_intents(hass)


@pytest.fixture
async def init_components(hass: HomeAssistant, tmp_path: Path) -> AsyncGenerator[None]:
    """Initialize relevant components with empty configs."""

    def preload_and_cache():
        custom_sentences_dir = Path(hass.config.path("custom_sentences/en"))
        os.mkdir(tmp_path / "en")
        for custom_sentences_path in custom_sentences_dir.rglob("*.yaml"):
            with (
                custom_sentences_path.open(encoding="utf-8") as custom_sentences_file,
                open(
                    tmp_path / "en" / os.path.basename(custom_sentences_file.name),
                    mode="w",
                    encoding="utf-8",
                ) as dest_file,
            ):
                dest_file.write(custom_sentences_file.read())

    await hass.async_add_executor_job(preload_and_cache)
    with patch(
        "homeassistant.components.conversation.default_agent.DefaultAgent._get_custom_sentences_path",
        return_value=tmp_path / "en",
    ):
        assert await async_setup_component(hass, "homeassistant", {})
        assert await async_setup_component(hass, "conversation", {})
        yield
