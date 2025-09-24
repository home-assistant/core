"""Analytics platform."""

from collections.abc import Mapping
from typing import Any

from homeassistant.components.analytics import (
    AnalyticsInput,
    AnalyticsModifications,
    EntityAnalyticsModifications,
)
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE_LIST,
    ATTR_SOUND_MODE_LIST,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import entity_registry as er

from .const import (
    OPTION_INPUT_SOURCES,
    OPTION_LISTENING_MODES,
    InputSource,
    ListeningMode,
)
from .util import get_meaning


async def async_modify_analytics(
    hass: HomeAssistant, analytics_input: AnalyticsInput
) -> AnalyticsModifications:
    """Modify the analytics."""
    ent_reg = er.async_get(hass)

    entities: dict[str, EntityAnalyticsModifications] = {}
    for entity_id in analytics_input.entity_ids:
        platform = split_entity_id(entity_id)[0]
        if platform != Platform.MEDIA_PLAYER:
            continue

        entity_entry = ent_reg.entities[entity_id]
        if entity_entry.capabilities is not None:
            config_entry_id = entity_entry.config_entry_id
            assert config_entry_id is not None
            config_entry = hass.config_entries.async_get_entry(config_entry_id)
            assert config_entry is not None

            capabilities = _anonymise_media_player_capabilities(
                entity_entry.capabilities, config_entry
            )
            if capabilities is None:
                continue

            entities[entity_id] = EntityAnalyticsModifications(
                capabilities=capabilities
            )

    return AnalyticsModifications(entities=entities)


def _anonymise_media_player_capabilities(
    capabilities: Mapping[str, Any], config_entry: ConfigEntry
) -> dict[str, Any] | None:
    """Anonymise media player capabilities for analytics."""
    user_sources = capabilities.get(ATTR_INPUT_SOURCE_LIST)
    user_sound_modes = capabilities.get(ATTR_SOUND_MODE_LIST)
    if user_sources is None and user_sound_modes is None:
        return None

    capabilities = dict(capabilities)

    if user_sources is not None:
        source_mapping = {
            v: get_meaning(InputSource(k))
            for k, v in config_entry.options.get(OPTION_INPUT_SOURCES, {}).items()
        }
        capabilities[ATTR_INPUT_SOURCE_LIST] = [
            source_mapping.get(user_source) for user_source in user_sources
        ]

    if user_sound_modes is not None:
        sound_mode_mapping = {
            v: get_meaning(ListeningMode(k))
            for k, v in config_entry.options.get(OPTION_LISTENING_MODES, {}).items()
        }
        capabilities[ATTR_SOUND_MODE_LIST] = [
            sound_mode_mapping.get(user_sound_mode)
            for user_sound_mode in user_sound_modes
        ]

    return capabilities
