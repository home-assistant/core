"""Test helpers for AI Task integration."""

import json

import pytest

from homeassistant.components.ai_task import (
    DOMAIN,
    AITaskEntity,
    AITaskEntityFeature,
    GenDataTask,
    GenDataTaskResult,
    GenImageTask,
    GenImageTaskResult,
)
from homeassistant.components.conversation import AssistantContent, ChatLog
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"
TEST_ENTITY_ID = "ai_task.test_task_entity"


class MockAITaskEntity(AITaskEntity):
    """Mock AI Task entity for testing."""

    _attr_name = "Test Task Entity"
    _attr_supported_features = (
        AITaskEntityFeature.GENERATE_DATA
        | AITaskEntityFeature.SUPPORT_ATTACHMENTS
        | AITaskEntityFeature.GENERATE_IMAGE
    )

    def __init__(self) -> None:
        """Initialize the mock entity."""
        super().__init__()
        self.mock_generate_data_tasks = []
        self.mock_generate_image_tasks = []

    async def _async_generate_data(
        self, task: GenDataTask, chat_log: ChatLog
    ) -> GenDataTaskResult:
        """Mock handling of generate data task."""
        self.mock_generate_data_tasks.append(task)
        if task.structure is not None:
            data = {"name": "Tracy Chen", "age": 30}
            data_chat_log = json.dumps(data)
        else:
            data = "Mock result"
            data_chat_log = data
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(self.entity_id, data_chat_log)
        )
        return GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=data,
        )

    async def _async_generate_image(
        self, task: GenImageTask, chat_log: ChatLog
    ) -> GenImageTaskResult:
        """Mock handling of generate image task."""
        self.mock_generate_image_tasks.append(task)
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(self.entity_id, "")
        )
        return GenImageTaskResult(
            conversation_id=chat_log.conversation_id,
            image_data=b"mock_image_data",
            mime_type="image/png",
            width=1536,
            height=1024,
            model="mock_model",
            revised_prompt="mock_revised_prompt",
        )


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a configuration entry for AI Task."""
    entry = MockConfigEntry(domain=TEST_DOMAIN, entry_id="mock-test-entry")
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_ai_task_entity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockAITaskEntity:
    """Mock AI Task entity."""
    return MockAITaskEntity()


@pytest.fixture
async def init_components(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ai_task_entity: MockAITaskEntity,
):
    """Initialize the AI Task integration with a mock entity."""
    assert await async_setup_component(hass, "homeassistant", {})

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.AI_TASK]
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload test config entry."""
        await hass.config_entries.async_forward_entry_unload(
            config_entry, Platform.AI_TASK
        )
        return True

    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test tts platform via config entry."""
        async_add_entities([mock_ai_task_entity])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, ConfigFlow):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
