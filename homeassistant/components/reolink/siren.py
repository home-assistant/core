"""Component providing support for Reolink siren entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_VOLUME_LEVEL,
    SirenEntity,
    SirenEntityDescription,
    SirenEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ReolinkChannelCoordinatorEntity, ReolinkChannelEntityDescription
from .util import ReolinkConfigEntry, ReolinkData, raise_translated_error

PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class ReolinkSirenEntityDescription(
    SirenEntityDescription, ReolinkChannelEntityDescription
):
    """A class that describes siren entities."""


SIREN_ENTITIES = (
    ReolinkSirenEntityDescription(
        key="siren",
        translation_key="siren",
        supported=lambda api, ch: api.supported(ch, "siren_play"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ReolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Reolink siren entities."""
    reolink_data: ReolinkData = config_entry.runtime_data

    async_add_entities(
        ReolinkSirenEntity(reolink_data, channel, entity_description)
        for entity_description in SIREN_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    )


class ReolinkSirenEntity(ReolinkChannelCoordinatorEntity, SirenEntity):
    """Base siren entity class for Reolink IP cameras."""

    _attr_supported_features = (
        SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.DURATION
        | SirenEntityFeature.VOLUME_SET
    )
    entity_description: ReolinkSirenEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkSirenEntityDescription,
    ) -> None:
        """Initialize Reolink siren entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data, channel)

    @raise_translated_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the siren."""
        if (volume := kwargs.get(ATTR_VOLUME_LEVEL)) is not None:
            await self._host.api.set_volume(self._channel, int(volume * 100))
        duration = kwargs.get(ATTR_DURATION)
        await self._host.api.set_siren(self._channel, True, duration)

    @raise_translated_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the siren."""
        await self._host.api.set_siren(self._channel, False, None)
