"""Support for monitoring pyLoad."""

from __future__ import annotations

from enum import StrEnum

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PyLoadConfigEntry
from .const import DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT, DOMAIN, ISSUE_PLACEHOLDER
from .coordinator import PyLoadCoordinator


class PyLoadSensorEntity(StrEnum):
    """pyLoad Sensor Entities."""

    SPEED = "speed"


SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=PyLoadSensorEntity.SPEED,
        translation_key=PyLoadSensorEntity.SPEED,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=1,
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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
            breaks_in_ha_version="2025.2.0",
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
            breaks_in_ha_version="2025.2.0",
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


class PyLoadSensor(CoordinatorEntity[PyLoadCoordinator], SensorEntity):
    """Representation of a pyLoad sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PyLoadCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize a new pyLoad sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self.entity_description = entity_description
        self.device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="PyLoad Team",
            model="pyLoad",
            configuration_url=coordinator.pyload.api_url,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            sw_version=coordinator.version,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data, self.entity_description.key)
