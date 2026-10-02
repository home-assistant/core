"""Integration tests for the Mistral AI config entry setup."""

from unittest.mock import patch

from homeassistant.components.mistral_ai import DOMAIN
from homeassistant.components.mistral_ai.const import (
    DEFAULT_CONVERSATION_NAME,
    RECOMMENDED_CONVERSATION_OPTIONS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


class _FakeModels:
    def list(self, timeout_ms=None) -> list:
        return []


class _FakeMistral:
    def __init__(self, api_key=None, async_client=None) -> None:
        self.models = _FakeModels()
        self.chat = None
        self.audio = None

    def __getattr__(self, name):
        # Lazy sub-SDK access used by _setup_client preload.
        if name in ("chat", "models", "audio"):
            return self.models
        raise AttributeError(name)


async def test_config_entry_creates_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Setting up the entry creates a conversation entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mistral",
        data={"api_key": "test-key"},
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

    # The conversation dependency needs the "homeassistant" component loaded
    # (it initializes the ExposedEntities registry).
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.mistral_ai._setup_client",
            return_value=_FakeMistral(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    states = hass.states.async_all()
    entity_ids = {state.entity_id for state in states}
    domains = {entity_id.split(".")[0] for entity_id in entity_ids}
    assert "conversation" in domains

    # Exactly one conversation entity from this integration.
    mistral_entities = [
        entity
        for entity in entity_registry.entities.values()
        if entity.platform == DOMAIN
    ]
    assert len(mistral_entities) == 1
