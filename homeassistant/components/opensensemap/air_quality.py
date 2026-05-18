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

from .const import CONF_STATION_ID, DOMAIN, INTEGRATION_TITLE
from .coordinator import OpenSenseMapConfigEntry, OpenSenseMapCoordinator

PLATFORM_SCHEMA = AIR_QUALITY_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_STATION_ID): cv.string, vol.Optional(CONF_NAME): cv.string}
)

KNOWN_IMPORT_ABORT_REASONS = {"cannot_connect", "invalid_station"}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import legacy YAML configuration into a config entry."""
    import_data: dict[str, str] = {CONF_STATION_ID: config[CONF_STATION_ID]}
    if CONF_NAME in config:
        import_data[CONF_NAME] = config[CONF_NAME]
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=import_data,
    )
    if result.get("type") is FlowResultType.ABORT:
        reason = result.get("reason")
        if reason in KNOWN_IMPORT_ABORT_REASONS:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{reason}",
                breaks_in_ha_version="2026.11.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{reason}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": INTEGRATION_TITLE,
                },
            )
            return
        if reason != "already_configured":
            return

    # The "deprecated_yaml" translation key is provided by Home Assistant core
    # under the "homeassistant" domain, so no matching key exists in this
    # integration's strings.json.
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
        return self.coordinator.api.pm2_5

    @property
    def particulate_matter_10(self) -> float | None:
        """Return the particulate matter 10 level."""
        return self.coordinator.api.pm10
