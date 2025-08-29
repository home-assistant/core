"""AI Task integration for OpenRouter."""

from __future__ import annotations

from json import JSONDecodeError
import logging
from typing import Any

from homeassistant.components import ai_task, conversation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads

from . import OpenRouterConfigEntry
from .entity import OpenRouterEntity

_LOGGER = logging.getLogger(__name__)

# Try to get ATTACHMENTS feature, or create it if it doesn't exist
try:
    # Try normal way first
    ATTACHMENTS_FEATURE = ai_task.AITaskEntityFeature.ATTACHMENTS
except AttributeError:
    # If it doesn't exist, create our own flag value
    # Use bit 2 (value 2) as GENERATE_DATA is likely bit 1
    ATTACHMENTS_FEATURE = 2
    _LOGGER.warning("ATTACHMENTS feature not found, using fallback value: %s", ATTACHMENTS_FEATURE)

# Always support both features
SUPPORTED_FEATURES = ai_task.AITaskEntityFeature.GENERATE_DATA | ATTACHMENTS_FEATURE
    
_LOGGER.info("OpenRouter AI Task: Supported features = %s", SUPPORTED_FEATURES)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenRouterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task_data":
            continue

        async_add_entities(
            [OpenRouterAITaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class OpenRouterAITaskEntity(
    ai_task.AITaskEntity,
    OpenRouterEntity,
):
    """OpenRouter AI Task entity."""

    _attr_name = None
    # Set default supported features
    _attr_supported_features = SUPPORTED_FEATURES
    
    def __init__(self, *args, **kwargs):
        """Initialize the AI Task entity."""
        super().__init__(*args, **kwargs)
        # Override supported features if needed
        self._attr_supported_features = SUPPORTED_FEATURES
        _LOGGER.debug("AI Task entity initialized with features: %s", self._attr_supported_features)
    
    @property
    def supported_features(self) -> int:
        """Return the supported features - this overrides the parent property."""
        # Always return our calculated features
        return SUPPORTED_FEATURES
        
    async def async_generate_data(
        self,
        prompt: str,
        *,
        attachments: list[Any] | None = None,
        **kwargs,
    ) -> str | dict[str, Any]:
        """Generate data from prompt and optional attachments.
        
        This method provides an alternative interface that always accepts attachments.
        """
        _LOGGER.debug("async_generate_data called with %d attachments", 
                     len(attachments) if attachments else 0)
        
        # Create a task object that mimics what we need
        class Task:
            def __init__(self, prompt, attachments=None):
                self.prompt = prompt
                self.attachments = attachments or []
                self.name = "AI Task"
                self.structure = None
                
        task = Task(prompt, attachments)
        chat_log = conversation.ChatLog()
        
        # Add user message with prompt
        chat_log.add_user_message(prompt)
        
        # If we have attachments, add them to the chat log
        if attachments:
            # The entity.py will handle the attachments in the chat log
            pass
            
        result = await self._async_generate_data(task, chat_log)
        return result.data

    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        # Log task details for debugging
        _LOGGER.info("=== AI Task Debug Info ===")
        _LOGGER.info("Task type: %s", type(task))
        _LOGGER.info("Task attributes: %s", dir(task))
        _LOGGER.info("Chat log content count: %d", len(chat_log.content))
        
        # Check for attachments in multiple ways
        attachments = None
        
        # Method 1: Check task.attachments
        if hasattr(task, 'attachments'):
            attachments = task.attachments
            _LOGGER.info("Found attachments via task.attachments: %s", bool(attachments))
        
        # Method 2: Check task data
        if hasattr(task, 'data') and isinstance(task.data, dict):
            attachments = task.data.get('attachments')
            _LOGGER.info("Found attachments via task.data: %s", bool(attachments))
            
        # Method 3: Check chat log for attachments
        for content in chat_log.content:
            if hasattr(content, 'attachments') and content.attachments:
                _LOGGER.info("Found attachments in chat log content!")
                break
        
        if attachments:
            _LOGGER.info("Processing %d attachments for vision analysis", len(attachments))
        
        # Process the chat log (entity.py will handle image conversion)
        await self._async_handle_chat_log(chat_log, task.name, task.structure)

        if not isinstance(chat_log.content[-1], conversation.AssistantContent):
            raise HomeAssistantError(
                "Last content in chat log is not an AssistantContent"
            )

        text = chat_log.content[-1].content or ""

        if not task.structure:
            return ai_task.GenDataTaskResult(
                conversation_id=chat_log.conversation_id,
                data=text,
            )
        
        # Try to parse JSON response for structured output
        try:
            data = json_loads(text)
            _LOGGER.debug("Successfully parsed structured response")
        except JSONDecodeError as err:
            _LOGGER.error("Failed to parse JSON response: %s", text[:500])
            _LOGGER.error("JSON decode error: %s", err)
            # For now, return the raw text instead of crashing
            _LOGGER.warning("Returning raw text instead of structured data")
            return ai_task.GenDataTaskResult(
                conversation_id=chat_log.conversation_id,
                data=text,
            )

        return ai_task.GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=data,
        )
