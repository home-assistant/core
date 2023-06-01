"""Test select entity."""

from __future__ import annotations

import pytest

from homeassistant.components.assist_pipeline import Pipeline
from homeassistant.components.assist_pipeline.pipeline import PipelineStorageCollection
from homeassistant.components.assist_pipeline.select import AssistPipelineSelect
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from tests.common import MockConfigEntry, MockPlatform, mock_entity_platform


class SelectPlatform(MockPlatform):
    """Fake select platform."""

    # pylint: disable=method-hidden
    async def async_setup_entry(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up fake select platform."""
        async_add_entities([AssistPipelineSelect(hass, "test")])


@pytest.fixture
async def init_select(hass: HomeAssistant, init_components) -> ConfigEntry:
    """Initialize select entity."""
    mock_entity_platform(hass, "select.assist_pipeline", SelectPlatform())
    config_entry = MockConfigEntry(domain="assist_pipeline")
    assert await hass.config_entries.async_forward_entry_setup(config_entry, "select")
    return config_entry


@pytest.fixture
async def pipeline_1(
    hass: HomeAssistant, init_select, pipeline_storage: PipelineStorageCollection
) -> Pipeline:
    """Create a pipeline."""
    return await pipeline_storage.async_create_item(
        {
            "name": "Test 1",
            "language": "en-US",
            "conversation_engine": None,
            "conversation_language": "en-US",
            "tts_engine": None,
            "tts_language": None,
            "tts_voice": None,
            "stt_engine": None,
            "stt_language": None,
        }
    )


@pytest.fixture
async def pipeline_2(
    hass: HomeAssistant, init_select, pipeline_storage: PipelineStorageCollection
) -> Pipeline:
    """Create a pipeline."""
    return await pipeline_storage.async_create_item(
        {
            "name": "Test 2",
            "language": "en-US",
            "conversation_engine": None,
            "conversation_language": "en-US",
            "tts_engine": None,
            "tts_language": None,
            "tts_voice": None,
            "stt_engine": None,
            "stt_language": None,
        }
    )


async def test_select_entity_changing_pipelines(
    hass: HomeAssistant,
    init_select: ConfigEntry,
    pipeline_1: Pipeline,
    pipeline_2: Pipeline,
    pipeline_storage: PipelineStorageCollection,
) -> None:
    """Test entity tracking pipeline changes."""
    config_entry = init_select  # nicer naming

    state = hass.states.get("select.assist_pipeline_test_pipeline")
    assert state is not None
    assert state.state == "preferred"
    assert state.attributes["options"] == [
        "preferred",
        "Home Assistant",
        pipeline_1.name,
        pipeline_2.name,
    ]

    # Change select to new pipeline
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.assist_pipeline_test_pipeline",
            "option": pipeline_2.name,
        },
        blocking=True,
    )

    state = hass.states.get("select.assist_pipeline_test_pipeline")
    assert state.state == pipeline_2.name

    # Reload config entry to test selected option persists
    assert await hass.config_entries.async_forward_entry_unload(config_entry, "select")
    assert await hass.config_entries.async_forward_entry_setup(config_entry, "select")

    state = hass.states.get("select.assist_pipeline_test_pipeline")
    assert state.state == pipeline_2.name

    # Remove selected pipeline
    await pipeline_storage.async_delete_item(pipeline_2.id)

    state = hass.states.get("select.assist_pipeline_test_pipeline")
    assert state.state == "preferred"
    assert state.attributes["options"] == [
        "preferred",
        "Home Assistant",
        pipeline_1.name,
    ]
