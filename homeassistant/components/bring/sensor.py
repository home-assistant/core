"""Sensor platform for the Bring! integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from bring_api import BringList, BringUserSettingsResponse
from bring_api.const import BRING_SUPPORTED_LOCALES

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import BringConfigEntry, BringData, BringDataUpdateCoordinator
from .entity import BringBaseEntity
from .util import list_language, sum_attributes

PARALLEL_UPDATES = 0


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
    LIST_ACCESS = "list_access"


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
        value_fn=(
            lambda lst, settings: x.lower()
            if (x := list_language(lst.lst.listUuid, settings))
            else None
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[x.lower() for x in BRING_SUPPORTED_LOCALES],
        device_class=SensorDeviceClass.ENUM,
    ),
    BringSensorEntityDescription(
        key=BringSensor.LIST_ACCESS,
        translation_key=BringSensor.LIST_ACCESS,
        value_fn=lambda lst, _: lst.content.status.value.lower(),
        entity_category=EntityCategory.DIAGNOSTIC,
        options=["registered", "shared", "invitation"],
        device_class=SensorDeviceClass.ENUM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data.data
    lists_added: set[str] = set()

    @callback
    def add_entities() -> None:
        """Add sensor entities."""
        nonlocal lists_added

        if new_lists := {lst.listUuid for lst in coordinator.lists} - lists_added:
            async_add_entities(
                BringSensorEntity(
                    coordinator,
                    bring_list,
                    description,
                )
                for description in SENSOR_DESCRIPTIONS
                for bring_list in coordinator.lists
                if bring_list.listUuid in new_lists
            )
            lists_added |= new_lists

    coordinator.async_add_listener(add_entities)
    add_entities()


class BringSensorEntity(BringBaseEntity, SensorEntity):
    """A sensor entity."""

    entity_description: BringSensorEntityDescription
    coordinator: BringDataUpdateCoordinator

    def __init__(
        self,
        coordinator: BringDataUpdateCoordinator,
        bring_list: BringList,
        entity_description: BringSensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, bring_list)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{self._list_uuid}_{self.entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""

        return self.entity_description.value_fn(
            self.coordinator.data[self._list_uuid],
            self.coordinator.user_settings,
        )
