"""Support for monitoring pyLoad."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    UnitOfDataRate,
    UnitOfInformation,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from . import PyLoadConfigEntry
from .const import (
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    ISSUE_PLACEHOLDER,
    UNIT_DOWNLOADS,
)
from .coordinator import PyLoadData
from .entity import BasePyLoadEntity


class PyLoadSensorEntity(StrEnum):
    """pyLoad Sensor Entities."""

    ACTIVE = "active"
    FREE_SPACE = "free_space"
    QUEUE = "queue"
    SPEED = "speed"
    TOTAL = "total"


@dataclass(kw_only=True, frozen=True)
class PyLoadSensorEntityDescription(SensorEntityDescription):
    """Describes pyLoad switch entity."""

    value_fn: Callable[[PyLoadData], StateType]


SENSOR_DESCRIPTIONS: tuple[PyLoadSensorEntityDescription, ...] = (
    PyLoadSensorEntityDescription(
        key=PyLoadSensorEntity.SPEED,
        translation_key=PyLoadSensorEntity.SPEED,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=1,
        value_fn=lambda data: data.speed,
    ),
    PyLoadSensorEntityDescription(
        key=PyLoadSensorEntity.ACTIVE,
        translation_key=PyLoadSensorEntity.ACTIVE,
        native_unit_of_measurement=UNIT_DOWNLOADS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.active,
    ),
    PyLoadSensorEntityDescription(
        key=PyLoadSensorEntity.QUEUE,
        translation_key=PyLoadSensorEntity.QUEUE,
        native_unit_of_measurement=UNIT_DOWNLOADS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.queue,
    ),
    PyLoadSensorEntityDescription(
        key=PyLoadSensorEntity.TOTAL,
        translation_key=PyLoadSensorEntity.TOTAL,
        native_unit_of_measurement=UNIT_DOWNLOADS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.total,
    ),
    PyLoadSensorEntityDescription(
        key=PyLoadSensorEntity.FREE_SPACE,
        translation_key=PyLoadSensorEntity.FREE_SPACE,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        value_fn=lambda data: data.free_space,
    ),
)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=["speed"]): vol.All(
            cv.ensure_list, [vol.In(PyLoadSensorEntity)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_USERNAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import config from yaml."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if (
        result.get("type") == FlowResultType.CREATE_ENTRY
        or result.get("reason") == "already_configured"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            breaks_in_ha_version="2025.1.0",
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "pyLoad",
            },
        )
    elif error := result.get("reason"):
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{error}",
            breaks_in_ha_version="2025.1.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{error}",
            translation_placeholders=ISSUE_PLACEHOLDER,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PyLoadConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pyLoad sensors."""

    coordinator = entry.runtime_data

    async_add_entities(
        (
            PyLoadSensor(
                coordinator=coordinator,
                entity_description=description,
            )
            for description in SENSOR_DESCRIPTIONS
        ),
    )


class PyLoadSensor(BasePyLoadEntity, SensorEntity):
    """Representation of a pyLoad sensor."""

    entity_description: PyLoadSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
