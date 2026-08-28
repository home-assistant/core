"""Sensor platform for Discogs."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import DiscogsConfigEntry, DiscogsData, DiscogsDataUpdateCoordinator

UNIT_RECORDS = "records"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
    }
)


@dataclass(frozen=True, kw_only=True)
class DiscogsSensorEntityDescription(SensorEntityDescription):
    """Describes a Discogs sensor entity."""

    value_fn: Callable[[DiscogsData], str | int | None]
    attrs_fn: Callable[[DiscogsData], dict[str, Any] | None]


ATTR_IDENTITY = "identity"

SENSOR_TYPES: tuple[DiscogsSensorEntityDescription, ...] = (
    DiscogsSensorEntityDescription(
        key="collection",
        translation_key="collection",
        native_unit_of_measurement=UNIT_RECORDS,
        value_fn=lambda data: data.collection_count,
        attrs_fn=lambda data: {ATTR_IDENTITY: data.username},
    ),
    DiscogsSensorEntityDescription(
        key="wantlist",
        translation_key="wantlist",
        native_unit_of_measurement=UNIT_RECORDS,
        value_fn=lambda data: data.wantlist_count,
        attrs_fn=lambda data: {ATTR_IDENTITY: data.username},
    ),
    DiscogsSensorEntityDescription(
        key="random_record",
        translation_key="random_record",
        value_fn=lambda data: data.random_record,
        attrs_fn=lambda data: {
            ATTR_IDENTITY: data.username,
            **(data.random_record_attrs or {}),
        },
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddConfigEntryEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import YAML configuration and forward to config flow."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={CONF_TOKEN: config[CONF_TOKEN]},
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DiscogsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Discogs sensor from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        DiscogsSensor(coordinator, description, entry.entry_id)
        for description in SENSOR_TYPES
    )


class DiscogsSensor(CoordinatorEntity[DiscogsDataUpdateCoordinator], SensorEntity):
    """Representation of a Discogs sensor."""

    entity_description: DiscogsSensorEntityDescription
    _attr_attribution = "Data provided by Discogs"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DiscogsDataUpdateCoordinator,
        description: DiscogsSensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.discogs.com",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
        )

    @property
    @override
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the extra state attributes."""
        return self.entity_description.attrs_fn(self.coordinator.data)
