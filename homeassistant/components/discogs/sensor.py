"""Sensor platform for Discogs."""

from typing import Any, override

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import DiscogsConfigEntry, DiscogsData, DiscogsDataUpdateCoordinator

ATTR_IDENTITY = "identity"

ICON_RECORD = "mdi:album"
ICON_PLAYER = "mdi:record-player"
UNIT_RECORDS = "records"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("monitored_conditions"): vol.All(cv.ensure_list, [cv.string]),
    }
)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="collection",
        translation_key="collection",
        icon=ICON_RECORD,
        native_unit_of_measurement=UNIT_RECORDS,
    ),
    SensorEntityDescription(
        key="wantlist",
        translation_key="wantlist",
        icon=ICON_RECORD,
        native_unit_of_measurement=UNIT_RECORDS,
    ),
    SensorEntityDescription(
        key="random_record",
        translation_key="random_record",
        icon=ICON_PLAYER,
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import YAML configuration and forward to config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "import"},
        data={
            CONF_TOKEN: config[CONF_TOKEN],
            "name": config.get("name", DEFAULT_NAME),
        },
    )

    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_import_issue_cannot_connect",
            breaks_in_ha_version="2027.2.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue_cannot_connect",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Discogs",
            },
        )
        return

    if result.get("type") is FlowResultType.CREATE_ENTRY:
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2027.2.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Discogs",
            },
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DiscogsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Discogs sensor from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        DiscogsSensor(coordinator, description) for description in SENSOR_TYPES
    )


class DiscogsSensor(CoordinatorEntity[DiscogsDataUpdateCoordinator], SensorEntity):
    """Representation of a Discogs sensor."""

    _attr_attribution = "Data provided by Discogs"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DiscogsDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.discogs.com",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=coordinator.config_entry.title,
        )

    @property
    def _data(self) -> DiscogsData:
        """Return coordinator data."""
        return self.coordinator.data

    @property
    @override
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        if self.entity_description.key == "collection":
            return self._data.collection_count
        if self.entity_description.key == "wantlist":
            return self._data.wantlist_count
        return self._data.random_record

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the extra state attributes."""
        if self.entity_description.key == "random_record" and self._data.random_record:
            return {
                ATTR_IDENTITY: self._data.username,
                **(self._data.random_record_attrs or {}),
            }
        return {ATTR_IDENTITY: self._data.username}
