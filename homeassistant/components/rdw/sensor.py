"""Support for RDW sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from vehicle import Vehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_LICENSE_PLATE, DOMAIN


@dataclass(frozen=True, kw_only=True)
class RDWSensorEntityDescription(SensorEntityDescription):
    """Describes RDW sensor entity."""

    value_fn: Callable[[Vehicle], date | str | float | None]


SENSORS: tuple[RDWSensorEntityDescription, ...] = (
    RDWSensorEntityDescription(
        key="apk_expiration",
        translation_key="apk_expiration",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda vehicle: vehicle.apk_expiration,
    ),
    RDWSensorEntityDescription(
        key="ascription_date",
        translation_key="ascription_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda vehicle: vehicle.ascription_date,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RDW sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        RDWSensorEntity(
            coordinator=coordinator,
            license_plate=entry.data[CONF_LICENSE_PLATE],
            description=description,
        )
        for description in SENSORS
    )


class RDWSensorEntity(CoordinatorEntity[DataUpdateCoordinator[Vehicle]], SensorEntity):
    """Defines an RDW sensor."""

    entity_description: RDWSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: DataUpdateCoordinator[Vehicle],
        license_plate: str,
        description: RDWSensorEntityDescription,
    ) -> None:
        """Initialize RDW sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{license_plate}_{description.key}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{license_plate}")},
            manufacturer=coordinator.data.brand,
            name=f"{coordinator.data.brand} {coordinator.data.license_plate}",
            model=coordinator.data.model,
            configuration_url=f"https://ovi.rdw.nl/default.aspx?kenteken={coordinator.data.license_plate}",
        )

    @property
    def native_value(self) -> date | str | float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
