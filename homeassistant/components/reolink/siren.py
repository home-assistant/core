"""Component providing support for Reolink siren entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import Host

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_VOLUME_LEVEL,
    SirenEntity,
    SirenEntityDescription,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkCoordinatorEntity


@dataclass
class ReolinkSirenEntityDescriptionMixin:
    """Mixin values for Reolink siren entities."""

    method: Callable[[Host, int, bool, int], Any]
    volume: Callable[[Host, int, int], Any]


@dataclass
class ReolinkSirenEntityDescription(
    SirenEntityDescription, ReolinkSirenEntityDescriptionMixin
):
    """A class that describes siren entities."""

    supported: Callable[[Host, int], bool] = lambda api, ch: True


async def async_set_siren(api, channel, on_off, duration):
    """Control the siren."""
    return await api.set_siren(channel, on_off, int(duration))


SIREN_ENTITIES = (
    ReolinkSirenEntityDescription(
        key="siren",
        name="Siren",
        icon="mdi:alarm-light",
        supported=lambda api, ch: api.supported(ch, "siren"),
        method=async_set_siren,
        volume=lambda api, ch, volume: api.set_volume(ch, int(volume)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink siren entities."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ReolinkSirenEntity(reolink_data, channel, entity_description)
        for entity_description in SIREN_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    )


class ReolinkSirenEntity(ReolinkCoordinatorEntity, SirenEntity):
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
        super().__init__(reolink_data, channel)
        self.entity_description = entity_description

        self._attr_unique_id = (
            f"{self._host.unique_id}_{self._channel}_{entity_description.key}"
        )

    async def async_turn_on(self, **kwargs):
        """Turn on the siren."""
        if (volume := kwargs.get(ATTR_VOLUME_LEVEL)) is not None:
            await self.entity_description.volume(
                self._host.api, self._channel, volume * 100
            )
        duration = kwargs.get(ATTR_DURATION)
        await self.entity_description.method(
            self._host.api, self._channel, True, duration
        )

    async def async_turn_off(self, **kwargs):
        """Turn off the siren."""
        await self.entity_description.method(self._host.api, self._channel, False, None)
