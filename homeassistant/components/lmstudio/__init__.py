"""The LM Studio integration."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .client import (
    LMStudioAuthError,
    LMStudioClient,
    LMStudioConnectionError,
    LMStudioResponseError,
)
from .const import DEFAULT_TIMEOUT, DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = (Platform.CONVERSATION, Platform.AI_TASK)


@dataclass(slots=True)
class LMStudioConversationState:
    """State for a conversation thread."""

    response_id: str | None = None
    model: str | None = None
    prompt_signature: str | None = None


@dataclass(slots=True)
class LMStudioConversationStore:
    """Track conversation state for LM Studio."""

    states: dict[str, LMStudioConversationState] = field(default_factory=dict)

    def get_previous_response_id(
        self, conversation_id: str, model: str, prompt_signature: str
    ) -> str | None:
        """Return a response id if it matches the current conversation state."""
        state = self.states.get(conversation_id)
        if state is None:
            return None
        if state.model != model or state.prompt_signature != prompt_signature:
            self.states.pop(conversation_id, None)
            return None
        return state.response_id

    def set_response_id(
        self, conversation_id: str, model: str, prompt_signature: str, response_id: str
    ) -> None:
        """Store the response id for a conversation."""
        self.states[conversation_id] = LMStudioConversationState(
            response_id=response_id,
            model=model,
            prompt_signature=prompt_signature,
        )

    def reset(self, conversation_id: str) -> None:
        """Clear stored state for a conversation."""
        self.states.pop(conversation_id, None)


@dataclass(slots=True)
class LMStudioRuntimeData:
    """Runtime data for the LM Studio integration."""

    client: LMStudioClient
    conversation_store: LMStudioConversationStore
    unavailable_logged: bool = False


type LMStudioConfigEntry = ConfigEntry[LMStudioRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: LMStudioConfigEntry) -> bool:
    """Set up LM Studio from a config entry."""
    base_url = entry.data[CONF_URL]
    api_key = entry.data.get(CONF_API_KEY)

    client = LMStudioClient(
        hass=hass,
        base_url=base_url,
        api_key=api_key,
        timeout=DEFAULT_TIMEOUT,
    )

    try:
        await client.async_list_models()
    except LMStudioAuthError as err:
        raise ConfigEntryAuthFailed(err) from err
    except (LMStudioConnectionError, LMStudioResponseError) as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = LMStudioRuntimeData(
        client=client,
        conversation_store=LMStudioConversationStore(),
        unavailable_logged=False,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LMStudioConfigEntry) -> bool:
    """Unload LM Studio."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(hass: HomeAssistant, entry: LMStudioConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
