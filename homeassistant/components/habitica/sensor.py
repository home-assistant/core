"""Support for Habitica sensors."""

from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, cast

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HabiticaConfigEntry
from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import HabiticaDataUpdateCoordinator
from .util import entity_used_in

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class HabitipySensorEntityDescription(SensorEntityDescription):
    """Habitipy Sensor Description."""

    value_path: list[str]


class HabitipySensorEntity(StrEnum):
    """Habitipy Entities."""

    DISPLAY_NAME = "display_name"
    HEALTH = "health"
    HEALTH_MAX = "health_max"
    MANA = "mana"
    MANA_MAX = "mana_max"
    EXPERIENCE = "experience"
    EXPERIENCE_MAX = "experience_max"
    LEVEL = "level"
    GOLD = "gold"
    CLASS = "class"


SENSOR_DESCRIPTIONS: dict[str, HabitipySensorEntityDescription] = {
    HabitipySensorEntity.DISPLAY_NAME: HabitipySensorEntityDescription(
        key=HabitipySensorEntity.DISPLAY_NAME,
        translation_key=HabitipySensorEntity.DISPLAY_NAME,
        value_path=["profile", "name"],
    ),
    HabitipySensorEntity.HEALTH: HabitipySensorEntityDescription(
        key=HabitipySensorEntity.HEALTH,
        translation_key=HabitipySensorEntity.HEALTH,
        native_unit_of_measurement="HP",
        suggested_display_precision=0,
        value_path=["stats", "hp"],
    ),
    HabitipySensorEntity.HEALTH_MAX: HabitipySensorEntityDescription(
        key=HabitipySensorEntity.HEALTH_MAX,
        translation_key=HabitipySensorEntity.HEALTH_MAX,
        native_unit_of_measurement="HP",
        entity_registry_enabled_default=False,
        value_path=["stats", "maxHealth"],
    ),
    HabitipySensorEntity.MANA: HabitipySensorEntityDescription(
        key=HabitipySensorEntity.MANA,
        translation_key=HabitipySensorEntity.MANA,
        native_unit_of_measurement="MP",
        suggested_display_precision=0,
        value_path=["stats", "mp"],
    ),
    HabitipySensorEntity.MANA_MAX: HabitipySensorEntityDescription(
        key=HabitipySensorEntity.MANA_MAX,
        translation_key=HabitipySensorEntity.MANA_MAX,
        native_unit_of_measurement="MP",
        value_path=["stats", "maxMP"],
    ),
    HabitipySensorEntity.EXPERIENCE: HabitipySensorEntityDescription(
        key=HabitipySensorEntity.EXPERIENCE,
        translation_key=HabitipySensorEntity.EXPERIENCE,
        native_unit_of_measurement="XP",
        value_path=["stats", "exp"],
    ),
    HabitipySensorEntity.EXPERIENCE_MAX: HabitipySensorEntityDescription(
        key=HabitipySensorEntity.EXPERIENCE_MAX,
        translation_key=HabitipySensorEntity.EXPERIENCE_MAX,
        native_unit_of_measurement="XP",
        value_path=["stats", "toNextLevel"],
    ),
    HabitipySensorEntity.LEVEL: HabitipySensorEntityDescription(
        key=HabitipySensorEntity.LEVEL,
        translation_key=HabitipySensorEntity.LEVEL,
        value_path=["stats", "lvl"],
    ),
    HabitipySensorEntity.GOLD: HabitipySensorEntityDescription(
        key=HabitipySensorEntity.GOLD,
        translation_key=HabitipySensorEntity.GOLD,
        native_unit_of_measurement="GP",
        suggested_display_precision=2,
        value_path=["stats", "gp"],
    ),
    HabitipySensorEntity.CLASS: HabitipySensorEntityDescription(
        key=HabitipySensorEntity.CLASS,
        translation_key=HabitipySensorEntity.CLASS,
        value_path=["stats", "class"],
        device_class=SensorDeviceClass.ENUM,
        options=["warrior", "healer", "wizard", "rogue"],
    ),
}

SensorType = namedtuple("SensorType", ["name", "icon", "unit", "path"])
TASKS_TYPES = {
    "habits": SensorType(
        "Habits", "mdi:clipboard-list-outline", "n_of_tasks", ["habit"]
    ),
    "dailys": SensorType(
        "Dailys", "mdi:clipboard-list-outline", "n_of_tasks", ["daily"]
    ),
    "todos": SensorType("TODOs", "mdi:clipboard-list-outline", "n_of_tasks", ["todo"]),
    "rewards": SensorType(
        "Rewards", "mdi:clipboard-list-outline", "n_of_tasks", ["reward"]
    ),
}

TASKS_MAP_ID = "id"
TASKS_MAP = {
    "repeat": "repeat",
    "challenge": "challenge",
    "group": "group",
    "frequency": "frequency",
    "every_x": "everyX",
    "streak": "streak",
    "counter_up": "counterUp",
    "counter_down": "counterDown",
    "next_due": "nextDue",
    "yester_daily": "yesterDaily",
    "completed": "completed",
    "collapse_checklist": "collapseChecklist",
    "type": "type",
    "notes": "notes",
    "tags": "tags",
    "value": "value",
    "priority": "priority",
    "start_date": "startDate",
    "days_of_month": "daysOfMonth",
    "weeks_of_month": "weeksOfMonth",
    "created_at": "createdAt",
    "text": "text",
    "is_due": "isDue",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HabiticaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the habitica sensors."""

    name = config_entry.data[CONF_NAME]
    coordinator = config_entry.runtime_data

    entities: list[SensorEntity] = [
        HabitipySensor(coordinator, description, config_entry)
        for description in SENSOR_DESCRIPTIONS.values()
    ]
    entities.extend(
        HabitipyTaskSensor(name, task_type, coordinator, config_entry)
        for task_type in TASKS_TYPES
    )
    async_add_entities(entities, True)


class HabitipySensor(CoordinatorEntity[HabiticaDataUpdateCoordinator], SensorEntity):
    """A generic Habitica sensor."""

    _attr_has_entity_name = True
    entity_description: HabitipySensorEntityDescription

    def __init__(
        self,
        coordinator: HabiticaDataUpdateCoordinator,
        entity_description: HabitipySensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize a generic Habitica sensor."""
        super().__init__(coordinator, context=entity_description.value_path[0])
        if TYPE_CHECKING:
            assert entry.unique_id
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.unique_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=NAME,
            name=entry.data[CONF_NAME],
            configuration_url=entry.data[CONF_URL],
            identifiers={(DOMAIN, entry.unique_id)},
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        data = self.coordinator.data.user
        for element in self.entity_description.value_path:
            data = data[element]
        return cast(StateType, data)


class HabitipyTaskSensor(
    CoordinatorEntity[HabiticaDataUpdateCoordinator], SensorEntity
):
    """A Habitica task sensor."""

    def __init__(self, name, task_name, coordinator, entry):
        """Initialize a generic Habitica task."""
        super().__init__(coordinator)
        self._name = name
        self._task_name = task_name
        self._task_type = TASKS_TYPES[task_name]
        self._state = None
        self._attr_unique_id = f"{entry.unique_id}_{task_name}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=NAME,
            name=entry.data[CONF_NAME],
            configuration_url=entry.data[CONF_URL],
            identifiers={(DOMAIN, entry.unique_id)},
        )

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._task_type.icon

    @property
    def name(self):
        """Return the name of the task."""
        return f"{DOMAIN}_{self._name}_{self._task_name}"

    @property
    def native_value(self):
        """Return the state of the device."""
        return len(
            [
                task
                for task in self.coordinator.data.tasks
                if task.get("type") in self._task_type.path
                and not task.get("completed")
            ]
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes of all user tasks."""
        attrs = {}

        # Map tasks to TASKS_MAP
        for received_task in self.coordinator.data.tasks:
            if received_task.get("type") in self._task_type.path:
                task_id = received_task[TASKS_MAP_ID]
                task = {}
                for map_key, map_value in TASKS_MAP.items():
                    if value := received_task.get(map_value):
                        task[map_key] = value
                attrs[task_id] = task
        return attrs

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._task_type.unit

    async def async_added_to_hass(self) -> None:
        """Raise issue when entity is registered and was not disabled."""
        if TYPE_CHECKING:
            assert self.unique_id
        if entity_id := er.async_get(self.hass).async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, self.unique_id
        ):
            if (
                self.enabled
                and self._task_name in ("todos", "dailys")
                and entity_used_in(self.hass, entity_id)
            ):
                async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"deprecated_task_entity_{self._task_name}",
                    breaks_in_ha_version="2025.2.0",
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_task_entity",
                    translation_placeholders={
                        "task_name": self._task_name,
                        "entity": entity_id,
                    },
                )
            else:
                async_delete_issue(
                    self.hass,
                    DOMAIN,
                    f"deprecated_task_entity_{self._task_name}",
                )
        await super().async_added_to_hass()
