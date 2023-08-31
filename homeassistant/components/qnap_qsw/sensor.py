"""Support for the QNAP QSW sensors."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from aioqsw.const import (
    QSD_FAN1_SPEED,
    QSD_FAN2_SPEED,
    QSD_LACP_PORTS,
    QSD_LINK,
    QSD_PORT_NUM,
    QSD_PORTS,
    QSD_PORTS_STATISTICS,
    QSD_PORTS_STATUS,
    QSD_RX_ERRORS,
    QSD_RX_OCTETS,
    QSD_RX_SPEED,
    QSD_SPEED,
    QSD_SYSTEM_BOARD,
    QSD_SYSTEM_SENSOR,
    QSD_SYSTEM_TIME,
    QSD_TEMP,
    QSD_TEMP_MAX,
    QSD_TX_OCTETS,
    QSD_TX_SPEED,
    QSD_UPTIME,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED

from .const import ATTR_MAX, DOMAIN, QSW_COORD_DATA, RPM
from .coordinator import QswDataCoordinator
from .entity import QswEntityDescription, QswEntityType, QswSensorEntity


@dataclass
class QswSensorEntityDescription(SensorEntityDescription, QswEntityDescription):
    """A class that describes QNAP QSW sensor entities."""

    attributes: dict[str, list[str]] | None = None
    qsw_type: QswEntityType | None = None
    sep_key: str = "_"


SENSOR_TYPES: Final[tuple[QswSensorEntityDescription, ...]] = (
    QswSensorEntityDescription(
        translation_key="fan_1_speed",
        icon="mdi:fan-speed-1",
        key=QSD_SYSTEM_SENSOR,
        native_unit_of_measurement=RPM,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_FAN1_SPEED,
    ),
    QswSensorEntityDescription(
        translation_key="fan_2_speed",
        icon="mdi:fan-speed-2",
        key=QSD_SYSTEM_SENSOR,
        native_unit_of_measurement=RPM,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_FAN2_SPEED,
    ),
    QswSensorEntityDescription(
        translation_key="ports",
        attributes={
            ATTR_MAX: [QSD_SYSTEM_BOARD, QSD_PORT_NUM],
        },
        entity_registry_enabled_default=False,
        icon="mdi:ethernet",
        key=QSD_PORTS_STATUS,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_LINK,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        translation_key="rx",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:download-network",
        key=QSD_PORTS_STATISTICS,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_RX_OCTETS,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        translation_key="rx_errors",
        icon="mdi:close-network",
        key=QSD_PORTS_STATISTICS,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_RX_ERRORS,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        translation_key="rx_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        icon="mdi:download-network",
        key=QSD_PORTS_STATISTICS,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_RX_SPEED,
    ),
    QswSensorEntityDescription(
        attributes={
            ATTR_MAX: [QSD_SYSTEM_SENSOR, QSD_TEMP_MAX],
        },
        device_class=SensorDeviceClass.TEMPERATURE,
        key=QSD_SYSTEM_SENSOR,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_TEMP,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        translation_key="tx",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:upload-network",
        key=QSD_PORTS_STATISTICS,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_TX_OCTETS,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        translation_key="tx_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        icon="mdi:upload-network",
        key=QSD_PORTS_STATISTICS,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_TX_SPEED,
    ),
    QswSensorEntityDescription(
        translation_key="uptime",
        icon="mdi:timer-outline",
        key=QSD_SYSTEM_TIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_UPTIME,
    ),
)

LACP_PORT_SENSOR_TYPES: Final[tuple[QswSensorEntityDescription, ...]] = (
    QswSensorEntityDescription(
        device_class=SensorDeviceClass.DATA_RATE,
        entity_registry_enabled_default=False,
        icon="mdi:speedometer",
        key=QSD_PORTS_STATUS,
        name="Link Speed",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        qsw_type=QswEntityType.LACP_PORT,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_SPEED,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        icon="mdi:download-network",
        key=QSD_PORTS_STATISTICS,
        name="RX",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        qsw_type=QswEntityType.LACP_PORT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_RX_OCTETS,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        icon="mdi:close-network",
        key=QSD_PORTS_STATISTICS,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="RX Errors",
        qsw_type=QswEntityType.LACP_PORT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_RX_ERRORS,
    ),
    QswSensorEntityDescription(
        device_class=SensorDeviceClass.DATA_RATE,
        entity_registry_enabled_default=False,
        icon="mdi:download-network",
        key=QSD_PORTS_STATISTICS,
        name="RX Speed",
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        qsw_type=QswEntityType.LACP_PORT,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_RX_SPEED,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        icon="mdi:upload-network",
        key=QSD_PORTS_STATISTICS,
        name="TX",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        qsw_type=QswEntityType.LACP_PORT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_TX_OCTETS,
    ),
    QswSensorEntityDescription(
        device_class=SensorDeviceClass.DATA_RATE,
        entity_registry_enabled_default=False,
        icon="mdi:upload-network",
        key=QSD_PORTS_STATISTICS,
        name="TX Speed",
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        qsw_type=QswEntityType.LACP_PORT,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_TX_SPEED,
    ),
)

PORT_SENSOR_TYPES: Final[tuple[QswSensorEntityDescription, ...]] = (
    QswSensorEntityDescription(
        device_class=SensorDeviceClass.DATA_RATE,
        entity_registry_enabled_default=False,
        icon="mdi:speedometer",
        key=QSD_PORTS_STATUS,
        name="Link Speed",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        qsw_type=QswEntityType.PORT,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_SPEED,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        icon="mdi:download-network",
        key=QSD_PORTS_STATISTICS,
        name="RX",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        qsw_type=QswEntityType.PORT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_RX_OCTETS,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        icon="mdi:close-network",
        key=QSD_PORTS_STATISTICS,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="RX Errors",
        qsw_type=QswEntityType.PORT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_RX_ERRORS,
    ),
    QswSensorEntityDescription(
        device_class=SensorDeviceClass.DATA_RATE,
        entity_registry_enabled_default=False,
        icon="mdi:download-network",
        key=QSD_PORTS_STATISTICS,
        name="RX Speed",
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        qsw_type=QswEntityType.PORT,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_RX_SPEED,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        icon="mdi:upload-network",
        key=QSD_PORTS_STATISTICS,
        name="TX",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        qsw_type=QswEntityType.PORT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_TX_OCTETS,
    ),
    QswSensorEntityDescription(
        device_class=SensorDeviceClass.DATA_RATE,
        entity_registry_enabled_default=False,
        icon="mdi:upload-network",
        key=QSD_PORTS_STATISTICS,
        name="TX Speed",
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        qsw_type=QswEntityType.PORT,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_TX_SPEED,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add QNAP QSW sensors from a config_entry."""
    coordinator: QswDataCoordinator = hass.data[DOMAIN][entry.entry_id][QSW_COORD_DATA]

    entities: list[QswSensor] = []

    for description in SENSOR_TYPES:
        if (
            description.key in coordinator.data
            and description.subkey in coordinator.data[description.key]
        ):
            entities.append(QswSensor(coordinator, description, entry))

    for description in LACP_PORT_SENSOR_TYPES:
        if (
            description.key not in coordinator.data
            or QSD_LACP_PORTS not in coordinator.data[description.key]
        ):
            continue

        for port_id, port_values in coordinator.data[description.key][
            QSD_LACP_PORTS
        ].items():
            if description.subkey not in port_values:
                continue

            _desc = replace(
                description,
                sep_key=f"_lacp_port_{port_id}_",
                name=f"LACP Port {port_id} {description.name}",
            )
            entities.append(QswSensor(coordinator, _desc, entry, port_id))

    for description in PORT_SENSOR_TYPES:
        if (
            description.key not in coordinator.data
            or QSD_PORTS not in coordinator.data[description.key]
        ):
            continue

        for port_id, port_values in coordinator.data[description.key][
            QSD_PORTS
        ].items():
            if description.subkey not in port_values:
                continue

            _desc = replace(
                description,
                sep_key=f"_port_{port_id}_",
                name=f"Port {port_id} {description.name}",
            )
            entities.append(QswSensor(coordinator, _desc, entry, port_id))

    async_add_entities(entities)


class QswSensor(QswSensorEntity, SensorEntity):
    """Define a QNAP QSW sensor."""

    entity_description: QswSensorEntityDescription

    def __init__(
        self,
        coordinator: QswDataCoordinator,
        description: QswSensorEntityDescription,
        entry: ConfigEntry,
        type_id: int | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, type_id)

        if description.name == UNDEFINED:
            self._attr_has_entity_name = True
        else:
            self._attr_name = f"{self.product} {description.name}"
        self._attr_unique_id = (
            f"{entry.unique_id}_{description.key}"
            f"{description.sep_key}{description.subkey}"
        )
        self.entity_description = description
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        value = self.get_device_value(
            self.entity_description.key,
            self.entity_description.subkey,
            self.entity_description.qsw_type,
        )
        self._attr_native_value = value
        super()._async_update_attrs()
