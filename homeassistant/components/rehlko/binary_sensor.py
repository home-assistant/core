"""Binary sensor platform for Rehlko integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DEVICE_DATA_DEVICES,
    DEVICE_DATA_ID,
    DEVICE_DATA_IS_CONNECTED,
    GENERATOR_DATA_DEVICE,
)
from .coordinator import RehlkoConfigEntry
from .entity import RehlkoEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class RehlkoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Rehlko binary sensor entities."""

    on_value: str | bool = True
    off_value: str | bool = False
    document_key: str | None = None
    connectivity_key: str | None = DEVICE_DATA_IS_CONNECTED


BINARY_SENSORS: tuple[RehlkoBinarySensorEntityDescription, ...] = (
    RehlkoBinarySensorEntityDescription(
        key=DEVICE_DATA_IS_CONNECTED,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        document_key=GENERATOR_DATA_DEVICE,
        # Entity is available when the device is disconnected
        connectivity_key=None,
    ),
    RehlkoBinarySensorEntityDescription(
        key="switchState",
        translation_key="auto_run",
        on_value="Auto",
        off_value="Off",
    ),
    RehlkoBinarySensorEntityDescription(
        key="engineOilPressureOk",
        translation_key="oil_pressure",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_value=False,
        off_value=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RehlkoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    homes = config_entry.runtime_data.homes
    coordinators = config_entry.runtime_data.coordinators
    async_add_entities(
        RehlkoBinarySensorEntity(
            coordinators[device_data[DEVICE_DATA_ID]],
            device_data[DEVICE_DATA_ID],
            device_data,
            sensor_description,
            document_key=sensor_description.document_key,
            connectivity_key=sensor_description.connectivity_key,
        )
        for home_data in homes
        for device_data in home_data[DEVICE_DATA_DEVICES]
        for sensor_description in BINARY_SENSORS
    )


class RehlkoBinarySensorEntity(RehlkoEntity, BinarySensorEntity):
    """Representation of a Binary Sensor."""

    entity_description: RehlkoBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if self._rehlko_value == self.entity_description.on_value:
            return True
        if self._rehlko_value == self.entity_description.off_value:
            return False
        _LOGGER.warning(
            "Unexpected value for %s: %s",
            self.entity_description.key,
            self._rehlko_value,
        )
        return None
