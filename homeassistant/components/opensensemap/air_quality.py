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
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STATION_ID, DOMAIN, INTEGRATION_TITLE
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
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2026.11.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
        return

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

    def __init__(self, coordinator: OpenSenseMapCoordinator) -> None:
        """Initialize the air quality entity."""
        super().__init__(coordinator)
        self._attr_name = coordinator.config_entry.title
        self._attr_unique_id = coordinator.config_entry.unique_id

    @property
    def particulate_matter_2_5(self) -> float | None:
        """Return the particulate matter 2.5 level."""
        return self.coordinator.api.pm2_5

    @property
    def particulate_matter_10(self) -> float | None:
        """Return the particulate matter 10 level."""
        return self.coordinator.api.pm10
