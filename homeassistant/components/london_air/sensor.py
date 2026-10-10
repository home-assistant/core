"""Sensor platform for the London Air integration."""

from typing import override

import probatio

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AUTHORITIES, CONF_LOCATIONS, DOMAIN, MANUFACTURER
from .coordinator import (
    LondonAirConfigEntry,
    LondonAirDataUpdateCoordinator,
    authority_status,
)

PARALLEL_UPDATES = 0

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
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2027.5.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "London Air",
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.5.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "London Air",
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
        LondonAirSensor(coordinator, authority)
        for authority in entry.data[CONF_LOCATIONS]
    )


class LondonAirSensor(CoordinatorEntity[LondonAirDataUpdateCoordinator], SensorEntity):
    """Sensor reporting the air quality band for a London authority."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_icon = "mdi:cloud-outline"

    def __init__(
        self,
        coordinator: LondonAirDataUpdateCoordinator,
        authority: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._authority = authority
        self._attr_unique_id = authority
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, authority)},
            name=authority,
            manufacturer=MANUFACTURER,
        )
        self._update_attributes()

    def _update_attributes(self) -> None:
        """Set the sensor attributes from the coordinator data."""
        site_data = self.coordinator.data[self._authority]
        self._attr_native_value = authority_status(site_data)
        self._attr_extra_state_attributes = {
            "sites": len(site_data),
            "updated": site_data[0]["updated"] if site_data else None,
            "data": site_data,
        }

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        self.async_write_ha_state()
