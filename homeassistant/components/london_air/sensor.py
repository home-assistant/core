"""Sensor for checking the status of London air."""

from typing import Any, override

import probatio
from pylondonair import NO_SPECIES_DATA, Site

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AUTHORITIES, CONF_LOCATIONS, DOMAIN, INTEGRATION_TITLE
from .coordinator import LondonAirConfigEntry, LondonAirCoordinator

BREAKS_IN_HA_VERSION = "2027.6.0"

MANUFACTURER = "Imperial College London"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Optional(CONF_LOCATIONS, default=AUTHORITIES): probatio.All(
            probatio.EnsureList(), [probatio.In(AUTHORITIES)]
        )
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the London Air sensor platform from YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if result["type"] is FlowResultType.ABORT:
        if (reason := result["reason"]) == "single_instance_allowed":
            # Additional YAML blocks abort as single-instance; merge their locations.
            entry = hass.config_entries.async_entries(DOMAIN)[0]
            existing = entry.data[CONF_LOCATIONS]
            additional = [loc for loc in config[CONF_LOCATIONS] if loc not in existing]
            if additional:
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_LOCATIONS: existing + additional},
                )
                await hass.config_entries.async_reload(entry.entry_id)
        else:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{reason}",
                breaks_in_ha_version=BREAKS_IN_HA_VERSION,
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key="deprecated_yaml_import_issue",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": INTEGRATION_TITLE,
                },
            )
            return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
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
    entry: LondonAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up London Air sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirSensor(coordinator, name) for name in entry.data[CONF_LOCATIONS]
    )


class AirSensor(CoordinatorEntity[LondonAirCoordinator], SensorEntity):
    """Single authority air sensor."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud-outline"
    _attr_name = "Air Quality"

    def __init__(self, coordinator: LondonAirCoordinator, name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = name
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, name)},
            manufacturer=MANUFACTURER,
            name=name,
        )
        self._attr_unique_id = name

    @property
    @override
    def native_value(self) -> str | None:
        """Return the current air quality status."""
        authority = self.coordinator.data.authorities.get(self._key)
        return authority.status if authority is not None else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return other details about the sensor state."""
        authority = self.coordinator.data.authorities.get(self._key)
        sites = authority.sites if authority is not None else ()
        site_data = [_site_to_dict(site) for site in sites]
        return {
            "updated": (
                sites[0].updated.strftime("%Y-%m-%d %H:%M:%S") if sites else None
            ),
            "sites": len(site_data),
            "data": site_data,
        }


def _site_to_dict(site: Site) -> dict[str, Any]:
    """Convert a library site into the attribute dict format."""
    pollutants: list[dict[str, str] | str] = [
        {
            "description": pollutant.description,
            "code": pollutant.code,
            "quality": pollutant.quality,
            "index": pollutant.index,
            "summary": pollutant.summary,
        }
        for pollutant in site.pollutants
    ]
    if not pollutants:
        pollutants = [NO_SPECIES_DATA]
    return {
        "updated": site.updated.strftime("%Y-%m-%d %H:%M:%S"),
        "latitude": site.latitude,
        "longitude": site.longitude,
        "site_code": site.site_code,
        "site_name": site.site_name,
        "site_type": site.site_type,
        "pollutants": pollutants,
        "pollutants_status": site.status,
        "number_of_pollutants": site.number_of_pollutants,
    }
