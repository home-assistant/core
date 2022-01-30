"""Sensor that can display the current Home Assistant versions."""
from __future__ import annotations

from typing import Any, Final

import voluptuous as vol
from voluptuous.schema_builder import Schema

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_SOURCE,
    CONF_BETA,
    CONF_IMAGE,
    CONF_SOURCE,
    DEFAULT_BETA,
    DEFAULT_IMAGE,
    DEFAULT_NAME,
    DEFAULT_SOURCE,
    DOMAIN,
    HOME_ASSISTANT,
    LOGGER,
    VALID_IMAGES,
    VALID_SOURCES,
)
from .coordinator import VersionDataUpdateCoordinator

PLATFORM_SCHEMA: Final[Schema] = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_BETA, default=DEFAULT_BETA): cv.boolean,
        vol.Optional(CONF_IMAGE, default=DEFAULT_IMAGE): vol.In(VALID_IMAGES),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SOURCE, default=DEFAULT_SOURCE): vol.In(VALID_SOURCES),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the legacy version sensor platform."""
    LOGGER.warning(
        "Configuration of the Version platform in YAML is deprecated and will be "
        "removed in Home Assistant 2022.4; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={ATTR_SOURCE: SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up version sensors."""
    coordinator: VersionDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if (entity_name := entry.data[CONF_NAME]) == DEFAULT_NAME:
        entity_name = entry.title

    version_sensor_entities: list[VersionSensorEntity] = [
        VersionSensorEntity(
            coordinator=coordinator,
            entity_description=SensorEntityDescription(
                key=str(entry.data[CONF_SOURCE]),
                name=entity_name,
            ),
        )
    ]

    async_add_entities(version_sensor_entities)


class VersionSensorEntity(CoordinatorEntity, SensorEntity):
    """Version sensor entity class."""

    _attr_icon = "mdi:package-up"
    _attr_device_info = DeviceInfo(
        name=f"{HOME_ASSISTANT} {DOMAIN.title()}",
        identifiers={(HOME_ASSISTANT, DOMAIN)},
        manufacturer=HOME_ASSISTANT,
        entry_type=DeviceEntryType.SERVICE,
    )

    coordinator: VersionDataUpdateCoordinator

    def __init__(
        self,
        coordinator: VersionDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize version sensor entities."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

    @property
    def native_value(self) -> StateType:
        """Return the native value of this sensor."""
        return self.coordinator.version

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes of this sensor."""
        return self.coordinator.version_data
