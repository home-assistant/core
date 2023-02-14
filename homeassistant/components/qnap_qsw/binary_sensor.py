"""Support for the QNAP QSW binary sensors."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from aioqsw.const import (
    QSD_ANOMALY,
    QSD_FIRMWARE_CONDITION,
    QSD_LACP_PORTS,
    QSD_LINK,
    QSD_MESSAGE,
    QSD_PORTS,
    QSD_PORTS_STATUS,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_MESSAGE, DOMAIN, QSW_COORD_DATA
from .coordinator import QswDataCoordinator
from .entity import QswEntityDescription, QswEntityType, QswSensorEntity


@dataclass
class QswBinarySensorEntityDescription(
    BinarySensorEntityDescription, QswEntityDescription
):
    """A class that describes QNAP QSW binary sensor entities."""

    attributes: dict[str, list[str]] | None = None
    qsw_type: QswEntityType | None = None
    sep_key: str = "_"


BINARY_SENSOR_TYPES: Final[tuple[QswBinarySensorEntityDescription, ...]] = (
    QswBinarySensorEntityDescription(
        attributes={
            ATTR_MESSAGE: [QSD_FIRMWARE_CONDITION, QSD_MESSAGE],
        },
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        key=QSD_FIRMWARE_CONDITION,
        name="Anomaly",
        subkey=QSD_ANOMALY,
    ),
)

LACP_PORT_BINARY_SENSOR_TYPES: Final[tuple[QswBinarySensorEntityDescription, ...]] = (
    QswBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=False,
        key=QSD_PORTS_STATUS,
        qsw_type=QswEntityType.LACP_PORT,
        name="Link",
        subkey=QSD_LINK,
    ),
)

PORT_BINARY_SENSOR_TYPES: Final[tuple[QswBinarySensorEntityDescription, ...]] = (
    QswBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=False,
        key=QSD_PORTS_STATUS,
        qsw_type=QswEntityType.PORT,
        name="Link",
        subkey=QSD_LINK,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add QNAP QSW binary sensors from a config_entry."""
    coordinator: QswDataCoordinator = hass.data[DOMAIN][entry.entry_id][QSW_COORD_DATA]

    entities: list[QswBinarySensor] = []

    for description in BINARY_SENSOR_TYPES:
        if (
            description.key in coordinator.data
            and description.subkey in coordinator.data[description.key]
        ):
            entities.append(QswBinarySensor(coordinator, description, entry))

    for description in LACP_PORT_BINARY_SENSOR_TYPES:
        if (
            description.key in coordinator.data
            and QSD_LACP_PORTS in coordinator.data[description.key]
        ):
            for port_id, port_values in coordinator.data[description.key][
                QSD_LACP_PORTS
            ].items():
                if description.subkey in port_values:
                    _desc = replace(
                        description,
                        sep_key=f"_lacp_port_{port_id}_",
                        name=f"LACP Port {port_id} {description.name}",
                    )
                    entities.append(QswBinarySensor(coordinator, _desc, entry, port_id))

    for description in PORT_BINARY_SENSOR_TYPES:
        if (
            description.key in coordinator.data
            and QSD_PORTS in coordinator.data[description.key]
        ):
            for port_id, port_values in coordinator.data[description.key][
                QSD_PORTS
            ].items():
                if description.subkey in port_values:
                    _desc = replace(
                        description,
                        sep_key=f"_port_{port_id}_",
                        name=f"Port {port_id} {description.name}",
                    )
                    entities.append(QswBinarySensor(coordinator, _desc, entry, port_id))

    async_add_entities(entities)


class QswBinarySensor(QswSensorEntity, BinarySensorEntity):
    """Define a QNAP QSW binary sensor."""

    entity_description: QswBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: QswDataCoordinator,
        description: QswBinarySensorEntityDescription,
        entry: ConfigEntry,
        type_id: int | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, type_id)

        self._attr_name = f"{self.product} {description.name}"
        self._attr_unique_id = (
            f"{entry.unique_id}_{description.key}"
            f"{description.sep_key}{description.subkey}"
        )
        self.entity_description = description
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update binary sensor attributes."""
        self._attr_is_on = self.get_device_value(
            self.entity_description.key,
            self.entity_description.subkey,
            self.entity_description.qsw_type,
        )
        super()._async_update_attrs()
