"""Sensor platform for the Bring! integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from bring_api import BringUserSettingsResponse
from bring_api.const import BRING_SUPPORTED_LOCALES

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import BringConfigEntry
from .coordinator import BringData, BringDataUpdateCoordinator
from .entity import BringBaseEntity
from .util import list_language, sum_attributes


@dataclass(kw_only=True, frozen=True)
class BringSensorEntityDescription(SensorEntityDescription):
    """Bring Sensor Description."""

    value_fn: Callable[[BringData, BringUserSettingsResponse], StateType]


class BringSensor(StrEnum):
    """Bring sensors."""

    URGENT = "urgent"
    CONVENIENT = "convenient"
    DISCOUNTED = "discounted"
    LIST_LANGUAGE = "list_language"


SENSOR_DESCRIPTIONS: tuple[BringSensorEntityDescription, ...] = (
    BringSensorEntityDescription(
        key=BringSensor.URGENT,
        translation_key=BringSensor.URGENT,
        value_fn=lambda lst, _: sum_attributes(lst, "urgent"),
    ),
    BringSensorEntityDescription(
        key=BringSensor.CONVENIENT,
        translation_key=BringSensor.CONVENIENT,
        value_fn=lambda lst, _: sum_attributes(lst, "convenient"),
    ),
    BringSensorEntityDescription(
        key=BringSensor.DISCOUNTED,
        translation_key=BringSensor.DISCOUNTED,
        value_fn=lambda lst, _: sum_attributes(lst, "discounted"),
    ),
    BringSensorEntityDescription(
        key=BringSensor.LIST_LANGUAGE,
        translation_key=BringSensor.LIST_LANGUAGE,
        value_fn=(lambda lst, settings: list_language(lst["listUuid"], settings)),
        entity_category=EntityCategory.DIAGNOSTIC,
        options=BRING_SUPPORTED_LOCALES,
        device_class=SensorDeviceClass.ENUM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BringConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data

    for bring_list in coordinator.data.values():
        async_add_entities(
            BringSensorEntity(
                coordinator,
                bring_list,
                description,
            )
            for description in SENSOR_DESCRIPTIONS
        )


class BringSensorEntity(BringBaseEntity, SensorEntity):
    """A sensor entity."""

    entity_description: BringSensorEntityDescription

    def __init__(
        self,
        coordinator: BringDataUpdateCoordinator,
        bring_list: BringData,
        entity_description: BringSensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = entity_description

        super().__init__(coordinator, bring_list)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""

        return self.entity_description.value_fn(
            self.coordinator.data[self._list_uuid],
            self.coordinator.user_settings,
        )
