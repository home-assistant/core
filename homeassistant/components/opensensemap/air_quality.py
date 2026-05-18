"""Support for openSenseMap Air Quality data."""

import voluptuous as vol

from homeassistant.components.air_quality import (
    PLATFORM_SCHEMA as AIR_QUALITY_PLATFORM_SCHEMA,
    AirQualityEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_STATION_ID,
    DOMAIN,
    INTEGRATION_TITLE,
    KNOWN_IMPORT_ABORT_REASONS,
)
from .coordinator import OpenSenseMapConfigEntry, OpenSenseMapCoordinator

PLATFORM_SCHEMA = AIR_QUALITY_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_STATION_ID): cv.string, vol.Optional(CONF_NAME): cv.string}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import legacy YAML configuration into a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={k: config[k] for k in (CONF_STATION_ID, CONF_NAME) if k in config},
    )

    if (
        result["type"] is FlowResultType.ABORT
        and result["reason"] in KNOWN_IMPORT_ABORT_REASONS
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version="2026.11.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )

    # "deprecated_yaml" translation key lives under the "homeassistant" core domain.
    # Always raised so users see the deprecation notice even when the import
    # fails — they need to remove the YAML block once they recover.
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2026.11.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenSenseMapConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the openSenseMap air quality entity from a config entry."""
    async_add_entities([OpenSenseMapQuality(entry.runtime_data)])


class OpenSenseMapQuality(CoordinatorEntity[OpenSenseMapCoordinator], AirQualityEntity):
    """Implementation of an openSenseMap air quality entity."""

    _attr_attribution = "Data provided by openSenseMap"
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: OpenSenseMapCoordinator) -> None:
        """Initialize the air quality entity."""
        super().__init__(coordinator)
        station_id = coordinator.config_entry.data[CONF_STATION_ID]
        self._attr_unique_id = station_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, station_id)},
            manufacturer=INTEGRATION_TITLE,
            name=coordinator.config_entry.title,
            configuration_url=f"https://opensensemap.org/explore/{station_id}",
        )

    @property
    def particulate_matter_2_5(self) -> float | None:
        """Return the particulate matter 2.5 level."""
        return self.coordinator.data.pm2_5

    @property
    def particulate_matter_10(self) -> float | None:
        """Return the particulate matter 10 level."""
        return self.coordinator.data.pm10
