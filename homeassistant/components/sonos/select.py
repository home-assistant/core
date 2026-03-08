"""Select entities for Sonos."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_DIALOG_LEVEL,
    ATTR_DIALOG_LEVEL_ENUM,
    MODEL_SONOS_ARC_ULTRA,
    SONOS_CREATE_SELECTS,
    SPEECH_DIALOG_LEVEL,
)
from .entity import SonosEntity
from .helpers import SonosConfigEntry, soco_error
from .speaker import SonosSpeaker


@dataclass(frozen=True, kw_only=True)
class SonosSelectEntityDescription(SelectEntityDescription):
    """Describes AirGradient select entity."""

    soco_attribute: str
    speaker_attribute: str
    speaker_model: str


SELECT_TYPES: list[SonosSelectEntityDescription] = [
    SonosSelectEntityDescription(
        key=SPEECH_DIALOG_LEVEL,
        translation_key=SPEECH_DIALOG_LEVEL,
        soco_attribute=ATTR_DIALOG_LEVEL,
        speaker_attribute=ATTR_DIALOG_LEVEL_ENUM,
        speaker_model=MODEL_SONOS_ARC_ULTRA,
        options=["off", "low", "medium", "high", "max"],
    ),
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SonosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sonos select platform from a config entry."""

    def available_soco_attributes(
        speaker: SonosSpeaker,
    ) -> list[SonosSelectEntityDescription]:
        features: list[SonosSelectEntityDescription] = []
        for select_data in SELECT_TYPES:
            if select_data.speaker_model == speaker.model_name.upper():
                if (
                    speaker.update_soco_int_attribute(
                        select_data.soco_attribute, select_data.speaker_attribute
                    )
                    is not None
                ):
                    features.append(select_data)
        return features

    async def _async_create_entities(speaker: SonosSpeaker) -> None:
        available_features = await hass.async_add_executor_job(
            available_soco_attributes, speaker
        )
        async_add_entities(
            SonosSelectEntity(speaker, config_entry, select_data)
            for select_data in available_features
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_SELECTS, _async_create_entities)
    )


class SonosSelectEntity(SonosEntity, SelectEntity):
    """Representation of a Sonos select entity."""

    def __init__(
        self,
        speaker: SonosSpeaker,
        config_entry: SonosConfigEntry,
        select_data: SonosSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-{select_data.key}"
        self._attr_translation_key = select_data.translation_key
        assert select_data.options is not None
        self._attr_options = select_data.options
        self.speaker_attribute = select_data.speaker_attribute
        self.soco_attribute = select_data.soco_attribute

    async def _async_fallback_poll(self) -> None:
        """Poll the value if subscriptions are not working."""
        await self.hass.async_add_executor_job(self.poll_state)
        self.async_write_ha_state()

    @soco_error()
    def poll_state(self) -> None:
        """Poll the device for the current state."""
        self.speaker.update_soco_int_attribute(
            self.soco_attribute, self.speaker_attribute
        )

    @property
    def current_option(self) -> str | None:
        """Return the current option for the entity."""
        option = getattr(self.speaker, self.speaker_attribute, None)
        if not isinstance(option, int) or not (0 <= option < len(self._attr_options)):
            _LOGGER.error(
                "Invalid option %s for %s on %s",
                option,
                self.soco_attribute,
                self.speaker.zone_name,
            )
            return None
        return self._attr_options[option]

    @soco_error()
    def select_option(self, option: str) -> None:
        """Set a new value."""
        dialog_level = self._attr_options.index(option)
        setattr(self.soco, self.soco_attribute, dialog_level)
