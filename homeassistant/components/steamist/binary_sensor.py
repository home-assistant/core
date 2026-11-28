"""Support for Steamist binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiosteamist import MODEL_550, SteamistStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SteamistConfigEntry
from .entity import SteamistEntity


@dataclass(frozen=True, kw_only=True)
class SteamistBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Steamist binary sensor entity."""

    is_on_fn: Callable[[SteamistStatus], bool]


STEAM_RUNNING_SENSOR = SteamistBinarySensorEntityDescription(
    key="steam_running",
    translation_key="steam_running",
    device_class=BinarySensorDeviceClass.RUNNING,
    is_on_fn=lambda status: status.steam_active,
)

SHOWER_RUNNING_SENSOR = SteamistBinarySensorEntityDescription(
    key="shower_running",
    translation_key="shower_running",
    device_class=BinarySensorDeviceClass.RUNNING,
    is_on_fn=lambda status: status.shower_active,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SteamistConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = config_entry.runtime_data
    descriptions: list[SteamistBinarySensorEntityDescription] = [STEAM_RUNNING_SENSOR]
    if (
        config_entry.data.get(CONF_MODEL) == MODEL_550
        or coordinator.client.model == MODEL_550
    ):
        descriptions.append(SHOWER_RUNNING_SENSOR)
    async_add_entities(
        [
            SteamistBinarySensorEntity(coordinator, config_entry, description)
            for description in descriptions
        ]
    )


class SteamistBinarySensorEntity(SteamistEntity, BinarySensorEntity):
    """Representation of a Steamist binary sensor."""

    entity_description: SteamistBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool:
        """Return if the binary sensor is active."""
        return self.entity_description.is_on_fn(self._status)
