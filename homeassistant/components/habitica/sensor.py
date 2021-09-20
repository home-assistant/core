"""Support for Habitica sensors."""
from collections import namedtuple
from datetime import timedelta
import logging

from aiohttp import ClientResponseError

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME, HTTP_TOO_MANY_REQUESTS
from homeassistant.util import Throttle

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

ST = SensorType = namedtuple("SensorType", ["name", "icon", "unit", "path"])

SENSORS_TYPES = {
    "name": ST("Name", None, "", ["profile", "name"]),
    "hp": ST("HP", "mdi:heart", "HP", ["stats", "hp"]),
    "maxHealth": ST("max HP", "mdi:heart", "HP", ["stats", "maxHealth"]),
    "mp": ST("Mana", "mdi:auto-fix", "MP", ["stats", "mp"]),
    "maxMP": ST("max Mana", "mdi:auto-fix", "MP", ["stats", "maxMP"]),
    "exp": ST("EXP", "mdi:star", "EXP", ["stats", "exp"]),
    "toNextLevel": ST("Next Lvl", "mdi:star", "EXP", ["stats", "toNextLevel"]),
    "lvl": ST("Lvl", "mdi:arrow-up-bold-circle-outline", "Lvl", ["stats", "lvl"]),
    "gp": ST("Gold", "mdi:circle-multiple", "Gold", ["stats", "gp"]),
    "class": ST("Class", "mdi:sword", "", ["stats", "class"]),
}

TASKS_TYPES = {
    "habits": ST("Habits", "mdi:clipboard-list-outline", "n_of_tasks", ["habits"]),
    "dailys": ST("Dailys", "mdi:clipboard-list-outline", "n_of_tasks", ["dailys"]),
    "todos": ST("TODOs", "mdi:clipboard-list-outline", "n_of_tasks", ["todos"]),
    "rewards": ST("Rewards", "mdi:clipboard-list-outline", "n_of_tasks", ["rewards"]),
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


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the habitica sensors."""

    entities = []
    name = config_entry.data[CONF_NAME]
    sensor_data = HabitipyData(hass.data[DOMAIN][config_entry.entry_id])
    await sensor_data.update()
    for sensor_type in SENSORS_TYPES:
        entities.append(HabitipySensor(name, sensor_type, sensor_data))
    for task_type in TASKS_TYPES:
        entities.append(HabitipyTaskSensor(name, task_type, sensor_data))
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
            if error.status == HTTP_TOO_MANY_REQUESTS:
                _LOGGER.warning(
                    "Sensor data update for %s has too many API requests;"
                    " Skipping the update",
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
                if error.status == HTTP_TOO_MANY_REQUESTS:
                    _LOGGER.warning(
                        "Sensor data update for %s has too many API requests;"
                        " Skipping the update",
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

    def __init__(self, name, sensor_name, updater):
        """Initialize a generic Habitica sensor."""
        self._name = name
        self._sensor_name = sensor_name
        self._sensor_type = SENSORS_TYPES[sensor_name]
        self._state = None
        self._updater = updater

    async def async_update(self):
        """Update Condition and Forecast."""
        await self._updater.update()
        data = self._updater.data
        for element in self._sensor_type.path:
            data = data[element]
        self._state = data

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._sensor_type.icon

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self._name}_{self._sensor_name}"

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._sensor_type.unit


class HabitipyTaskSensor(SensorEntity):
    """A Habitica task sensor."""

    def __init__(self, name, task_name, updater):
        """Initialize a generic Habitica task."""
        self._name = name
        self._task_name = task_name
        self._task_type = TASKS_TYPES[task_name]
        self._state = None
        self._updater = updater

    async def async_update(self):
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
                    value = received_task.get(map_value)
                    if value:
                        task[map_key] = value
                attrs[task_id] = task
            return attrs

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._task_type.unit
