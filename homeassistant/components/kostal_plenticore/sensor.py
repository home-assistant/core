"""Platform for Kostal Plenticore sensors."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ICON, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_ENABLED_DEFAULT, DOMAIN, SENSOR_PROCESS_DATA
from .helper import PlenticoreDataFormatter, ProcessDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add kostal plenticore Sensors."""
    plenticore = hass.data[DOMAIN][entry.entry_id]

    entities = []

    available_process_data = await plenticore.client.get_process_data()
    process_data_update_coordinator = ProcessDataUpdateCoordinator(
        hass,
        _LOGGER,
        "Process Data",
        timedelta(seconds=10),
        plenticore,
    )
    module_id: str
    data_id: str
    name: str
    sensor_data: dict[str, Any]
    fmt: str
    for (  # type: ignore[assignment]
        module_id,
        data_id,
        name,
        sensor_data,
        fmt,
    ) in SENSOR_PROCESS_DATA:
        if (
            module_id not in available_process_data
            or data_id not in available_process_data[module_id]
        ):
            _LOGGER.debug(
                "Skipping non existing process data %s/%s", module_id, data_id
            )
            continue

        entities.append(
            PlenticoreDataSensor(
                process_data_update_coordinator,
                entry.entry_id,
                entry.title,
                module_id,
                data_id,
                name,
                sensor_data,
                PlenticoreDataFormatter.get_method(fmt),
                plenticore.device_info,
                None,
            )
        )

    async_add_entities(entities)


class PlenticoreDataSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Plenticore data Sensor."""

    def __init__(
        self,
        coordinator,
        entry_id: str,
        platform_name: str,
        module_id: str,
        data_id: str,
        sensor_name: str,
        sensor_data: dict[str, Any],
        formatter: Callable[[str], Any],
        device_info: DeviceInfo,
        entity_category: EntityCategory | None,
    ):
        """Create a new Sensor Entity for Plenticore process data."""
        super().__init__(coordinator)
        self.entry_id = entry_id
        self.platform_name = platform_name
        self.module_id = module_id
        self.data_id = data_id

        self._sensor_name = sensor_name
        self._sensor_data = sensor_data
        self._formatter = formatter

        self._device_info = device_info

        self._attr_entity_category = entity_category

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.module_id in self.coordinator.data
            and self.data_id in self.coordinator.data[self.module_id]
        )

    async def async_added_to_hass(self) -> None:
        """Register this entity on the Update Coordinator."""
        await super().async_added_to_hass()
        self.coordinator.start_fetch_data(self.module_id, self.data_id)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from the Update Coordinator."""
        self.coordinator.stop_fetch_data(self.module_id, self.data_id)
        await super().async_will_remove_from_hass()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self._device_info

    @property
    def unique_id(self) -> str:
        """Return the unique id of this Sensor Entity."""
        return f"{self.entry_id}_{self.module_id}_{self.data_id}"

    @property
    def name(self) -> str:
        """Return the name of this Sensor Entity."""
        return f"{self.platform_name} {self._sensor_name}"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of this Sensor Entity or None."""
        return self._sensor_data.get(ATTR_UNIT_OF_MEASUREMENT)

    @property
    def icon(self) -> str | None:
        """Return the icon name of this Sensor Entity or None."""
        return self._sensor_data.get(ATTR_ICON)

    @property
    def device_class(self) -> str | None:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._sensor_data.get(ATTR_DEVICE_CLASS)

    @property
    def state_class(self) -> str | None:
        """Return the class of the state of this device, from component STATE_CLASSES."""
        return self._sensor_data.get(ATTR_STATE_CLASS)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._sensor_data.get(ATTR_ENABLED_DEFAULT, False)

    @property
    def native_value(self) -> Any | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            # None is translated to STATE_UNKNOWN
            return None

        raw_value = self.coordinator.data[self.module_id][self.data_id]

        return self._formatter(raw_value) if self._formatter else raw_value
