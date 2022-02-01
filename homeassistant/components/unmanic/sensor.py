"""Sensor platform for Unmanic."""
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, NAME
from .entity import UnmanicEntity

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="total-workers",
        name=f"{NAME} Total Workers",
        icon="mdi:account-hard-hat",
        native_unit_of_measurement="workers",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="active-workers",
        name=f"{NAME} Active Workers",
        icon="mdi:account-hard-hat",
        native_unit_of_measurement="workers",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="queue",
        name=f"{NAME} Pending Tasks",
        icon="mdi:clipboard-text-clock",
        native_unit_of_measurement="files",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="history",
        name=f"{NAME} Completed Tasks",
        icon="mdi:clipboard-check",
        native_unit_of_measurement="files",
        entity_registry_enabled_default=True,
    ),
)


async def async_setup_entry(hass, entry, async_add_devices):
    """Unmanic setup sensor entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_devices(
        [UnmanicSensor(coordinator, entry, description) for description in SENSORS],
        True,
    )


class UnmanicSensor(UnmanicEntity, SensorEntity):
    """Unmanic Sensor class."""

    def __init__(self, coordinator, config_entry, description) -> None:
        """Initialize."""
        self.coordinator = coordinator
        self.config_entry = config_entry
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"
        self.key = description.key

        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            device_id=config_entry.entry_id,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.key == "total-workers":
            return self.coordinator.data.get("settings").number_of_workers
        if self.key == "active-workers":
            return len(self.coordinator.data.get("workers_status"))
        if self.key == "queue":
            return self.coordinator.data.get("pending_tasks").recordsTotal
        if self.key == "history":
            return self.coordinator.data.get("task_history").recordsTotal
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        if self.key == "total-workers":
            for worker in self.coordinator.data.get("workers_status"):
                attrs[worker.id + "_name"] = worker.name
                attrs[worker.id + "_idle"] = worker.idle
                attrs[worker.id + "_pasued"] = worker.paused
                attrs[worker.id + "_start_time"] = worker.start_time
                attrs[worker.id + "_current_file"] = worker.current_file
                attrs[worker.id + "_current_task"] = worker.current_task
        elif self.key == "active-workers":
            for worker in self.coordinator.data.get("workers_status"):
                if not worker.idle:
                    attrs[worker.id + "_name"] = worker.name
                    attrs[worker.id + "_idle"] = worker.idle
                    attrs[worker.id + "_pasued"] = worker.paused
                    attrs[worker.id + "_start_time"] = worker.start_time
                    attrs[worker.id + "_current_file"] = worker.current_file
                    attrs[worker.id + "_current_task"] = worker.current_task
        elif self.key == "queue":
            attrs["records_filtered"] = self.coordinator.data.get(
                "pending_tasks"
            ).recordsFiltered
            media_num = 0
            for task in self.coordinator.data.get("pending_tasks").results:
                attrs["Task" + str(media_num) + "_id"] = task.id
                attrs["Task" + str(media_num) + "_abspath"] = task.abspath
                attrs["Task" + str(media_num) + "_priority"] = task.priority
                attrs["Task" + str(media_num) + "_type"] = task.type
                attrs["Task" + str(media_num) + "_status"] = task.status
                media_num += 1
        elif self.key == "history":
            attrs["records_filtered"] = self.coordinator.data.get(
                "task_history"
            ).recordsFiltered
            media_num = 0
            for task in self.coordinator.data.get("task_history").results:
                attrs["Task" + str(media_num) + "_id"] = task.id
                attrs["Task" + str(media_num) + "_task_label"] = task.task_label
                attrs["Task" + str(media_num) + "_task_success"] = task.task_success
                attrs["Task" + str(media_num) + "_finish_time"] = task.finish_time
                media_num += 1

        return attrs
