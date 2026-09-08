"""Support for Gatus sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import override

from gatus_api import EndpointStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GatusConfigEntry, GatusDataUpdateCoordinator
from .entity import GatusEndpointEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GatusSensorEntityDescription(SensorEntityDescription):
    """Class describing Gatus sensor entities."""

    value_fn: Callable[
        [GatusDataUpdateCoordinator, EndpointStatus],
        datetime | float | int | str | None,
    ]


DNS_RCODE_MAP = {
    "NOERROR": "no_error",
    "FORMERR": "format_error",
    "SERVFAIL": "server_failure",
    "NXDOMAIN": "non_existent_domain",
    "NOTIMP": "not_implemented",
    "REFUSED": "refused",
}


SENSOR_TYPES: tuple[GatusSensorEntityDescription, ...] = (
    GatusSensorEntityDescription(
        key="response_time",
        translation_key="response_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator, endpoint: (
            round(endpoint.results[-1].duration / 1_000_000, 2)
            if endpoint.results and endpoint.results[-1].duration is not None
            else None
        ),
    ),
    GatusSensorEntityDescription(
        key="status_code",
        translation_key="status_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator, endpoint: (
            endpoint.results[-1].status if endpoint.results else None
        ),
    ),
    GatusSensorEntityDescription(
        key="last_event",
        translation_key="last_event",
        device_class=SensorDeviceClass.ENUM,
        options=["start", "healthy", "unhealthy", "resolved"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator, endpoint: (
            endpoint.events[-1].type.lower() if endpoint.events else None
        ),
    ),
    GatusSensorEntityDescription(
        key="certificate_expiration",
        translation_key="certificate_expiration",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator, endpoint: (
            coordinator.last_update_time
            + timedelta(
                seconds=endpoint.results[-1].certificate_expiration // 1_000_000_000
            )
            if endpoint.results
            and endpoint.results[-1].certificate_expiration is not None
            else None
        ),
    ),
    GatusSensorEntityDescription(
        key="dns_rcode",
        translation_key="dns_rcode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator, endpoint: (
            DNS_RCODE_MAP.get(
                endpoint.results[-1].dns_rcode,
                endpoint.results[-1].dns_rcode.lower(),
            )
            if endpoint.results and endpoint.results[-1].dns_rcode is not None
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GatusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Gatus sensor platform."""
    coordinator = entry.runtime_data

    async_add_entities(
        GatusEndpointSensor(coordinator, entry, endpoint_key, description)
        for endpoint_key, endpoint in coordinator.data.items()
        for description in SENSOR_TYPES
        if (
            description.key != "certificate_expiration"
            or (
                endpoint.results
                and endpoint.results[-1].certificate_expiration is not None
            )
        )
        and (
            description.key != "dns_rcode"
            or (endpoint.results and endpoint.results[-1].dns_rcode is not None)
        )
    )


class GatusEndpointSensor(GatusEndpointEntity, SensorEntity):
    """Representation of a Gatus endpoint sensor."""

    entity_description: GatusSensorEntityDescription

    def __init__(
        self,
        coordinator: GatusDataUpdateCoordinator,
        entry: GatusConfigEntry,
        endpoint_key: str,
        description: GatusSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, endpoint_key)
        self.entity_description = description
        self._attr_translation_key = description.translation_key
        self._attr_unique_id = f"{entry.entry_id}_{endpoint_key}_{description.key}"

    @property
    @override
    def native_value(self) -> datetime | float | int | str | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator, self.endpoint_data)
