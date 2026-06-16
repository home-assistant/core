"""PrusaLink binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from pyprusalink.types import JobInfo, PrinterInfo, PrinterStatus, StatusInfo
from pyprusalink.types_legacy import LegacyPrinterStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PrusaLinkConfigEntry, PrusaLinkUpdateCoordinator
from .entity import PrusaLinkEntity, PrusaLinkEntityDescription


@dataclass(frozen=True, kw_only=True)
class PrusaLinkBinarySensorEntityDescription[
    T: (PrinterStatus, LegacyPrinterStatus, JobInfo, PrinterInfo)
](
    BinarySensorEntityDescription,
    PrusaLinkEntityDescription,
):
    """Describes PrusaLink sensor entity."""

    value_fn: Callable[[T], bool]


BINARY_SENSORS: dict[str, tuple[PrusaLinkBinarySensorEntityDescription, ...]] = {
    "status": (
        PrusaLinkBinarySensorEntityDescription[PrinterStatus](
            key="printer.status_connect",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            value_fn=lambda data: cast(
                bool, cast(StatusInfo, data["printer"]["status_connect"])["ok"]
            ),
            supported_fn=lambda data: (
                data["printer"].get("status_connect") is not None
                and data["printer"]["status_connect"].get("ok") is not None
            ),
        ),
    ),
    "info": (
        PrusaLinkBinarySensorEntityDescription[PrinterInfo](
            key="info.mmu",
            translation_key="mmu",
            value_fn=lambda data: data["mmu"],
            entity_registry_enabled_default=False,
        ),
        PrusaLinkBinarySensorEntityDescription[PrinterInfo](
            key="info.sd_ready",
            translation_key="sd_ready",
            value_fn=lambda data: data["sd_ready"],
            supported_fn=lambda data: data.get("sd_ready") is not None,
            entity_registry_enabled_default=False,
        ),
        PrusaLinkBinarySensorEntityDescription[PrinterInfo](
            key="info.farm_mode",
            translation_key="farm_mode",
            value_fn=lambda data: data["farm_mode"],
            supported_fn=lambda data: data.get("farm_mode") is not None,
            entity_registry_enabled_default=False,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PrusaLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PrusaLink sensor based on a config entry."""
    coordinators = entry.runtime_data

    entities: list[PrusaLinkEntity] = []
    for coordinator_type, binary_sensors in BINARY_SENSORS.items():
        coordinator = coordinators[coordinator_type]
        entities.extend(
            PrusaLinkBinarySensorEntity(coordinator, sensor_description)
            for sensor_description in binary_sensors
            if sensor_description.supported_fn(coordinator.data)
        )

    async_add_entities(entities)


class PrusaLinkBinarySensorEntity(PrusaLinkEntity, BinarySensorEntity):
    """Defines a PrusaLink binary sensor."""

    entity_description: PrusaLinkBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: PrusaLinkUpdateCoordinator,
        description: PrusaLinkBinarySensorEntityDescription,
    ) -> None:
        """Initialize a PrusaLink sensor entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
