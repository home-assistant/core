"""Sensor platform for the Bring! integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from bring_api import BringUserSettingsResponse
from bring_api.const import BRING_SUPPORTED_LOCALES
from bring_api.types import BringList

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import BringConfigEntry
from .const import DOMAIN
from .coordinator import BringData, BringDataUpdateCoordinator
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
            if (x := list_language(lst["uuid"], settings))
            else None
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[x.lower() for x in BRING_SUPPORTED_LOCALES],
        device_class=SensorDeviceClass.ENUM,
    ),
    BringSensorEntityDescription(
        key=BringSensor.LIST_ACCESS,
        translation_key=BringSensor.LIST_ACCESS,
        value_fn=lambda lst, _: lst["status"].lower(),
        entity_category=EntityCategory.DIAGNOSTIC,
        options=["registered", "shared", "invitation"],
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
    lists_added: set[str] = set()

    @callback
    def add_entities() -> None:
        """Add or remove sensor entities."""
        nonlocal lists_added
        entities: list[BringSensorEntity] = []
        entity_registry = er.async_get(hass)

        for bring_list in coordinator.lists:
            if bring_list["listUuid"] not in lists_added:
                entities.extend(
                    BringSensorEntity(
                        coordinator,
                        bring_list,
                        description,
                    )
                    for description in SENSOR_DESCRIPTIONS
                )
            lists_added.add(bring_list["listUuid"])

        user = {x["listUuid"] for x in coordinator.user_settings["userlistsettings"]}
        for list_uuid in user | lists_added:
            if any(
                bring_list["listUuid"] == list_uuid for bring_list in coordinator.lists
            ):
                continue

            for description in SENSOR_DESCRIPTIONS:
                if entity_id := entity_registry.async_get_entity_id(
                    SENSOR_DOMAIN,
                    DOMAIN,
                    f"{coordinator.config_entry.unique_id}_{list_uuid}_{description.key}",
                ):
                    entity_registry.async_remove(entity_id)

            lists_added.discard(list_uuid)

        if entities:
            async_add_entities(entities)

    coordinator.async_add_listener(add_entities)
    add_entities()


class BringSensorEntity(BringBaseEntity, SensorEntity):
    """A sensor entity."""

    entity_description: BringSensorEntityDescription

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

        if list_data := next(
            filter(lambda x: x["uuid"] == self._list_uuid, self.coordinator.data), None
        ):
            return self.entity_description.value_fn(
                list_data,
                self.coordinator.user_settings,
            )
        return None
