"""Support for the QNAP QSW sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
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
    QSD_UPTIME_SECONDS,
    QSD_UPTIME_TIMESTAMP,
)

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
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
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, StateType
from homeassistant.util import dt as dt_util

from .const import ATTR_MAX, DOMAIN, QSW_COORD_DATA, RPM
from .coordinator import QswDataCoordinator
from .entity import QswEntityDescription, QswEntityType, QswSensorEntity


@dataclass(frozen=True)
class QswSensorEntityDescription(SensorEntityDescription, QswEntityDescription):
    """A class that describes QNAP QSW sensor entities."""

    attributes: dict[str, list[str]] | None = None
    qsw_type: QswEntityType | None = None
    sep_key: str = "_"
    value_fn: Callable[[str], datetime | StateType] = lambda value: value


DEPRECATED_UPTIME_SECONDS = QswSensorEntityDescription(
    translation_key="uptime",
    key=QSD_SYSTEM_TIME,
    entity_category=EntityCategory.DIAGNOSTIC,
    native_unit_of_measurement=UnitOfTime.SECONDS,
    state_class=SensorStateClass.TOTAL_INCREASING,
    subkey=QSD_UPTIME_SECONDS,
)


SENSOR_TYPES: Final[tuple[QswSensorEntityDescription, ...]] = (
    QswSensorEntityDescription(
        translation_key="fan_1_speed",
        key=QSD_SYSTEM_SENSOR,
        native_unit_of_measurement=RPM,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_FAN1_SPEED,
    ),
    QswSensorEntityDescription(
        translation_key="fan_2_speed",
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
        key=QSD_PORTS_STATUS,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_LINK,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        translation_key="rx",
        device_class=SensorDeviceClass.DATA_SIZE,
        key=QSD_PORTS_STATISTICS,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_RX_OCTETS,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        translation_key="rx_errors",
        key=QSD_PORTS_STATISTICS,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_RX_ERRORS,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        translation_key="rx_speed",
        device_class=SensorDeviceClass.DATA_RATE,
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
        key=QSD_PORTS_STATISTICS,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_TX_OCTETS,
    ),
    QswSensorEntityDescription(
        entity_registry_enabled_default=False,
        translation_key="tx_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        key=QSD_PORTS_STATISTICS,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_TX_SPEED,
    ),
    QswSensorEntityDescription(
        translation_key="uptime_timestamp",
        key=QSD_SYSTEM_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        subkey=QSD_UPTIME_TIMESTAMP,
        value_fn=dt_util.parse_datetime,
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

    entities: list[QswSensor] = [
        QswSensor(coordinator, description, entry)
        for description in SENSOR_TYPES
        if (
            description.key in coordinator.data
            and description.subkey in coordinator.data[description.key]
        )
    ]

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

    # Can be removed in HA 2025.5.0
    entity_reg = er.async_get(hass)
    reg_entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)
    for entity in reg_entities:
        if entity.domain == "sensor" and entity.unique_id.endswith(
            ("_uptime", "_uptime_seconds")
        ):
            entity_id = entity.entity_id

            if entity.disabled:
                entity_reg.async_remove(entity_id)
                continue

            if (
                DEPRECATED_UPTIME_SECONDS.key in coordinator.data
                and DEPRECATED_UPTIME_SECONDS.subkey
                in coordinator.data[DEPRECATED_UPTIME_SECONDS.key]
            ):
                entities.append(
                    QswSensor(coordinator, DEPRECATED_UPTIME_SECONDS, entry)
                )

                entity_automations = automations_with_entity(hass, entity_id)
                entity_scripts = scripts_with_entity(hass, entity_id)

                for item in entity_automations + entity_scripts:
                    ir.async_create_issue(
                        hass,
                        DOMAIN,
                        f"uptime_seconds_deprecated_{entity_id}_{item}",
                        breaks_in_ha_version="2025.5.0",
                        is_fixable=False,
                        severity=ir.IssueSeverity.WARNING,
                        translation_key="uptime_seconds_deprecated",
                        translation_placeholders={
                            "entity": entity_id,
                            "info": item,
                        },
                    )

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
        self._attr_native_value = self.entity_description.value_fn(value)
        super()._async_update_attrs()
