"""Select entities for Sonos."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_DIALOG_LEVEL,
    ATTR_DIALOG_LEVEL_ENUM,
    MODEL_SONOS_ARC_ULTRA,
    SONOS_CREATE_SELECTS,
)
from .entity import SonosEntity
from .helpers import SonosConfigEntry, soco_error
from .speaker import SonosSpeaker


@dataclass(frozen=True)
class SonosSelectType:
    """Data class for Sonos select types."""

    feature: str
    attribute: str
    model: str
    options: list[str]


SELECT_TYPES: list[SonosSelectType] = [
    SonosSelectType(
        feature=ATTR_DIALOG_LEVEL,
        attribute=ATTR_DIALOG_LEVEL_ENUM,
        model=MODEL_SONOS_ARC_ULTRA,
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

    def available_soco_attributes(speaker: SonosSpeaker) -> list[SonosSelectType]:
        features: list[SonosSelectType] = []
        for select_data in SELECT_TYPES:
            if select_data.model == speaker.model_name.upper():
                if (
                    state := getattr(speaker.soco, select_data.feature, None)
                ) is not None:
                    setattr(speaker, select_data.attribute, state)
                    features.append(select_data)
        return features

    async def _async_create_entities(speaker: SonosSpeaker) -> None:
        entities = []

        available_features = await hass.async_add_executor_job(
            available_soco_attributes, speaker
        )

        for select_data in available_features:
            _LOGGER.debug(
                "Creating %s select control on %s attribute %s",
                select_data.feature,
                speaker.zone_name,
                select_data.attribute,
            )
            entities.append(SonosSelectEntity(speaker, config_entry, select_data))
        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_SELECTS, _async_create_entities)
    )


class SonosSelectEntity(SonosEntity, SelectEntity):
    """Representation of a Sonos select entity."""

    def __init__(
        self,
        speaker: SonosSpeaker,
        config_entry: SonosConfigEntry,
        select_data: SonosSelectType,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(speaker, config_entry)
        self.feature = select_data.feature
        self._attr_unique_id = f"{self.soco.uid}-select-{self.feature}"
        self._attr_translation_key = self.feature
        self.attribute = select_data.attribute
        self._attr_options = select_data.options

    async def _async_fallback_poll(self) -> None:
        """Poll the value if subscriptions are not working."""
        await self.hass.async_add_executor_job(self.poll_state)
        await self.async_write_ha_state()        

    @soco_error()
    def poll_state(self) -> None:
        """Poll the device for the current state."""
        state = getattr(self.soco, self.feature)
        setattr(self.speaker, self.attribute, state)

    @property
    def current_option(self) -> str | None:
        """Return the current option for the entity."""
        option = getattr(self.speaker, self.attribute, None)
        if not isinstance(option, int) or not (0 <= option < len(self._attr_options)):
            _LOGGER.error(
                "Invalid option index %s for %s on %s",
                option,
                self.feature,
                self.speaker.zone_name,
            )
            return None
        return self._attr_options[option]

    @soco_error()
    def select_option(self, option: str) -> None:
        """Set a new value."""
        dialog_level = self._attr_options.index(option)
        setattr(self.soco, self.feature, dialog_level)
