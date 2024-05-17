"""Binary sensors for System Monitor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
import logging
import sys
from typing import Literal

from psutil import NoSuchProcess

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import SystemMonitorConfigEntry
from .const import CONF_PROCESS, DOMAIN
from .coordinator import SystemMonitorCoordinator

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


def get_process(entity: SystemMonitorSensor) -> bool:
    """Return process."""
    state = False
    for proc in entity.coordinator.data.processes:
        try:
            _LOGGER.debug("process %s for argument %s", proc.name(), entity.argument)
            if entity.argument == proc.name():
                state = True
                break
        except NoSuchProcess as err:
            _LOGGER.warning(
                "Failed to load process with ID: %s, old name: %s",
                err.pid,
                err.name,
            )
    return state


@dataclass(frozen=True, kw_only=True)
class SysMonitorBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes System Monitor binary sensor entities."""

    value_fn: Callable[[SystemMonitorSensor], bool]
    add_to_update: Callable[[SystemMonitorSensor], tuple[str, str]]


SENSOR_TYPES: tuple[SysMonitorBinarySensorEntityDescription, ...] = (
    SysMonitorBinarySensorEntityDescription(
        key="binary_process",
        translation_key="process",
        icon=get_cpu_icon(),
        value_fn=get_process,
        device_class=BinarySensorDeviceClass.RUNNING,
        add_to_update=lambda entity: ("processes", ""),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemMonitorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up System Montor binary sensors based on a config entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        SystemMonitorSensor(
            coordinator,
            sensor_description,
            entry.entry_id,
            argument,
        )
        for sensor_description in SENSOR_TYPES
        for argument in entry.options.get(BINARY_SENSOR_DOMAIN, {}).get(
            CONF_PROCESS, []
        )
    )


class SystemMonitorSensor(
    CoordinatorEntity[SystemMonitorCoordinator], BinarySensorEntity
):
    """Implementation of a system monitor binary sensor."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description: SysMonitorBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SystemMonitorCoordinator,
        sensor_description: SysMonitorBinarySensorEntityDescription,
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

    async def async_added_to_hass(self) -> None:
        """When added to hass."""
        self.coordinator.update_subscribers[
            self.entity_description.add_to_update(self)
        ].add(self.entity_id)
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """When removed from hass."""
        self.coordinator.update_subscribers[
            self.entity_description.add_to_update(self)
        ].remove(self.entity_id)
        return await super().async_will_remove_from_hass()

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self)
