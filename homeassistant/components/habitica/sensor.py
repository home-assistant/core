"""Support for Habitica sensors."""

from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass
from datetime import timedelta
from http import HTTPStatus
import logging

from aiohttp import ClientResponseError

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .const import DOMAIN, MANUFACTURER, NAME

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

SensorType = namedtuple("SensorType", ["name", "icon", "unit", "path"])

SENSORS_TYPES = {
    "name": SensorType("Name", None, None, ["profile", "name"]),
    "hp": SensorType("HP", "mdi:heart", "HP", ["stats", "hp"]),
    "maxHealth": SensorType("max HP", "mdi:heart", "HP", ["stats", "maxHealth"]),
    "mp": SensorType("Mana", "mdi:auto-fix", "MP", ["stats", "mp"]),
    "maxMP": SensorType("max Mana", "mdi:auto-fix", "MP", ["stats", "maxMP"]),
    "exp": SensorType("EXP", "mdi:star", "EXP", ["stats", "exp"]),
    "toNextLevel": SensorType("Next Lvl", "mdi:star", "EXP", ["stats", "toNextLevel"]),
    "lvl": SensorType(
        "Lvl", "mdi:arrow-up-bold-circle-outline", "Lvl", ["stats", "lvl"]
    ),
    "gp": SensorType("Gold", "mdi:circle-multiple", "Gold", ["stats", "gp"]),
    "class": SensorType("Class", "mdi:sword", None, ["stats", "class"]),
}


@dataclass(kw_only=True, frozen=True)
class HabitipySensorEntityDescription(SensorEntityDescription):
    """Habitipy Sensor Description."""

    value_path: list[str]


SENSOR_DESCRIPTIONS: dict[str, HabitipySensorEntityDescription] = {
    "name": HabitipySensorEntityDescription(
        key="name",
        translation_key="name",
        value_path=["profile", "name"],
    ),
    "hp": HabitipySensorEntityDescription(
        key="hp",
        translation_key="hp",
        native_unit_of_measurement="HP",
        suggested_display_precision=0,
        value_path=["stats", "hp"],
    ),
    "maxHealth": HabitipySensorEntityDescription(
        key="maxHealth",
        translation_key="maxhealth",
        native_unit_of_measurement="HP",
        value_path=["stats", "maxHealth"],
    ),
    "mp": HabitipySensorEntityDescription(
        key="mp",
        translation_key="mp",
        native_unit_of_measurement="MP",
        suggested_display_precision=0,
        value_path=["stats", "mp"],
    ),
    "maxMP": HabitipySensorEntityDescription(
        key="maxMP",
        translation_key="maxmp",
        native_unit_of_measurement="MP",
        value_path=["stats", "maxMP"],
    ),
    "exp": HabitipySensorEntityDescription(
        key="exp",
        translation_key="exp",
        native_unit_of_measurement="XP",
        value_path=["stats", "exp"],
    ),
    "toNextLevel": HabitipySensorEntityDescription(
        key="toNextLevel",
        translation_key="tonextlevel",
        native_unit_of_measurement="XP",
        value_path=["stats", "toNextLevel"],
    ),
    "lvl": HabitipySensorEntityDescription(
        key="lvl",
        translation_key="lvl",
        native_unit_of_measurement="Lvl",
        value_path=["stats", "lvl"],
    ),
    "gp": HabitipySensorEntityDescription(
        key="gp",
        translation_key="gp",
        native_unit_of_measurement="🜚",  # alchemy symbol for gold
        suggested_display_precision=2,
        value_path=["stats", "gp"],
    ),
    "class": HabitipySensorEntityDescription(
        key="class",
        translation_key="class",
        value_path=["stats", "class"],
    ),
}

TASKS_TYPES = {
    "habits": SensorType(
        "Habits", "mdi:clipboard-list-outline", "n_of_tasks", ["habits"]
    ),
    "dailys": SensorType(
        "Dailys", "mdi:clipboard-list-outline", "n_of_tasks", ["dailys"]
    ),
    "todos": SensorType("TODOs", "mdi:clipboard-list-outline", "n_of_tasks", ["todos"]),
    "rewards": SensorType(
        "Rewards", "mdi:clipboard-list-outline", "n_of_tasks", ["rewards"]
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
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the habitica sensors."""

    name = config_entry.data[CONF_NAME]
    sensor_data = HabitipyData(hass.data[DOMAIN][config_entry.entry_id])
    await sensor_data.update()

    entities: list[SensorEntity] = [
        HabitipySensor(sensor_data, description, config_entry)
        for description in SENSOR_DESCRIPTIONS.values()
    ]
    entities.extend(
        HabitipyTaskSensor(name, task_type, sensor_data) for task_type in TASKS_TYPES
    )
    async_add_entities(entities, True)


class HabitipyData:
    """Habitica API user data cache."""

    def __init__(self, api):
        """Habitica API user data cache."""
        self.api = api
        self.data = None
        self.tasks = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self):
        """Get a new fix from Habitica servers."""
        try:
            self.data = await self.api.user.get()
        except ClientResponseError as error:
            if error.status == HTTPStatus.TOO_MANY_REQUESTS:
                _LOGGER.warning(
                    (
                        "Sensor data update for %s has too many API requests;"
                        " Skipping the update"
                    ),
                    DOMAIN,
                )
            else:
                _LOGGER.error(
                    "Count not update sensor data for %s (%s)",
                    DOMAIN,
                    error,
                )

        for task_type in TASKS_TYPES:
            try:
                self.tasks[task_type] = await self.api.tasks.user.get(type=task_type)
            except ClientResponseError as error:
                if error.status == HTTPStatus.TOO_MANY_REQUESTS:
                    _LOGGER.warning(
                        (
                            "Sensor data update for %s has too many API requests;"
                            " Skipping the update"
                        ),
                        DOMAIN,
                    )
                else:
                    _LOGGER.error(
                        "Count not update sensor data for %s (%s)",
                        DOMAIN,
                        error,
                    )


class HabitipySensor(SensorEntity):
    """A generic Habitica sensor."""

    _attr_has_entity_name = True
    entity_description: HabitipySensorEntityDescription

    def __init__(
        self,
        updater,
        entity_description: HabitipySensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize a generic Habitica sensor."""
        super().__init__()
        assert entry.unique_id
        self._updater = updater
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

    async def async_update(self) -> None:
        """Update Condition and Forecast."""
        await self._updater.update()
        data = self._updater.data
        for element in self.entity_description.value_path:
            data = data[element]
        self._attr_native_value = data


class HabitipyTaskSensor(SensorEntity):
    """A Habitica task sensor."""

    def __init__(self, name, task_name, updater):
        """Initialize a generic Habitica task."""
        self._name = name
        self._task_name = task_name
        self._task_type = TASKS_TYPES[task_name]
        self._state = None
        self._updater = updater

    async def async_update(self) -> None:
        """Update Condition and Forecast."""
        await self._updater.update()
        all_tasks = self._updater.tasks
        for element in self._task_type.path:
            tasks_length = len(all_tasks[element])
        self._state = tasks_length

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
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of all user tasks."""
        if self._updater.tasks is not None:
            all_received_tasks = self._updater.tasks
            for element in self._task_type.path:
                received_tasks = all_received_tasks[element]
            attrs = {}

            # Map tasks to TASKS_MAP
            for received_task in received_tasks:
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
