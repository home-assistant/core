"""Binary sensors for System Monitor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
import logging
import sys
from typing import Generic, Literal

import psutil

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import CONF_PROCESS, DOMAIN
from .coordinator import MonitorCoordinator, SystemMonitorProcessCoordinator, dataT

_LOGGER = logging.getLogger(__name__)

CONF_ARG = "arg"


SENSOR_TYPE_NAME = 0
SENSOR_TYPE_UOM = 1
SENSOR_TYPE_ICON = 2
SENSOR_TYPE_DEVICE_CLASS = 3
SENSOR_TYPE_MANDATORY_ARG = 4

SIGNAL_SYSTEMMONITOR_UPDATE = "systemmonitor_update"


@lru_cache
def get_cpu_icon() -> Literal["mdi:cpu-64-bit", "mdi:cpu-32-bit"]:
    """Return cpu icon."""
    if sys.maxsize > 2**32:
        return "mdi:cpu-64-bit"
    return "mdi:cpu-32-bit"


def get_process(entity: SystemMonitorSensor[list[psutil.Process]]) -> bool:
    """Return process."""
    state = False
    for proc in entity.coordinator.data:
        try:
            _LOGGER.debug("process %s for argument %s", proc.name(), entity.argument)
            if entity.argument == proc.name():
                state = True
                break
        except psutil.NoSuchProcess as err:
            _LOGGER.warning(
                "Failed to load process with ID: %s, old name: %s",
                err.pid,
                err.name,
            )
    return state


@dataclass(frozen=True, kw_only=True)
class SysMonitorBinarySensorEntityDescription(
    BinarySensorEntityDescription, Generic[dataT]
):
    """Describes System Monitor binary sensor entities."""

    value_fn: Callable[[SystemMonitorSensor[dataT]], bool]


SENSOR_TYPES: tuple[
    SysMonitorBinarySensorEntityDescription[list[psutil.Process]], ...
] = (
    SysMonitorBinarySensorEntityDescription[list[psutil.Process]](
        key="binary_process",
        translation_key="process",
        icon=get_cpu_icon(),
        value_fn=get_process,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up System Montor binary sensors based on a config entry."""
    entities: list[SystemMonitorSensor] = []
    process_coordinator = SystemMonitorProcessCoordinator(hass, "Process coordinator")
    await process_coordinator.async_request_refresh()

    for sensor_description in SENSOR_TYPES:
        _entry = entry.options.get(BINARY_SENSOR_DOMAIN, {})
        for argument in _entry.get(CONF_PROCESS, []):
            entities.append(
                SystemMonitorSensor(
                    process_coordinator,
                    sensor_description,
                    entry.entry_id,
                    argument,
                )
            )
    async_add_entities(entities)


class SystemMonitorSensor(
    CoordinatorEntity[MonitorCoordinator[dataT]], BinarySensorEntity
):
    """Implementation of a system monitor binary sensor."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description: SysMonitorBinarySensorEntityDescription[dataT]

    def __init__(
        self,
        coordinator: MonitorCoordinator[dataT],
        sensor_description: SysMonitorBinarySensorEntityDescription[dataT],
        entry_id: str,
        argument: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = sensor_description
        self._attr_translation_placeholders = {"process": argument}
        self._attr_unique_id: str = slugify(f"{sensor_description.key}_{argument}")
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="System Monitor",
            name="System Monitor",
        )
        self.argument = argument

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self)
