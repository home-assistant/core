"""Support for Rova garbage calendar."""

from __future__ import annotations

from datetime import datetime

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOUSE_NUMBER, CONF_HOUSE_NUMBER_SUFFIX, CONF_ZIP_CODE, DOMAIN
from .coordinator import RovaCoordinator

ISSUE_PLACEHOLDER = {"url": "/config/integrations/dashboard/add?domain=rova"}

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="gft",
        translation_key="bio",
    ),
    SensorEntityDescription(
        key="papier",
        translation_key="paper",
    ),
    SensorEntityDescription(
        key="pmd",
        translation_key="plastic",
    ),
    SensorEntityDescription(
        key="restafval",
        translation_key="residual",
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ZIP_CODE): cv.string,
        vol.Required(CONF_HOUSE_NUMBER): cv.string,
        vol.Optional(CONF_HOUSE_NUMBER_SUFFIX, default=""): cv.string,
        vol.Optional(CONF_NAME, default="Rova"): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["bio"]): vol.All(
            cv.ensure_list, [vol.In(["bio", "paper", "plastic", "residual"])]
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the rova sensor platform through yaml configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )
    if (
        result["type"] == FlowResultType.CREATE_ENTRY
        or result["reason"] == "already_configured"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.10.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Rova",
            },
        )
    else:
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version="2024.10.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
            translation_placeholders=ISSUE_PLACEHOLDER,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Rova entry."""
    coordinator: RovaCoordinator = hass.data[DOMAIN][entry.entry_id]

    assert entry.unique_id
    unique_id = entry.unique_id

    async_add_entities(
        RovaSensor(unique_id, description, coordinator) for description in SENSOR_TYPES
    )


class RovaSensor(CoordinatorEntity[RovaCoordinator], SensorEntity):
    """Representation of a Rova sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        description: SensorEntityDescription,
        coordinator: RovaCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)
