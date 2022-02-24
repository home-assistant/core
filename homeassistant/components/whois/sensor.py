"""Get WHOIS information for a given host."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast

from whois import Domain

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, TIME_DAYS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTR_EXPIRES, ATTR_NAME_SERVERS, ATTR_REGISTRAR, ATTR_UPDATED, DOMAIN


@dataclass
class WhoisSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Domain], datetime | int | str | None]


@dataclass
class WhoisSensorEntityDescription(
    SensorEntityDescription, WhoisSensorEntityDescriptionMixin
):
    """Describes a Whois sensor entity."""


def _days_until_expiration(domain: Domain) -> int | None:
    """Calculate days left until domain expires."""
    if domain.expiration_date is None:
        return None
    # We need to cast here, as (unlike Pyright) mypy isn't able to determine the type.
    return cast(int, (domain.expiration_date - domain.expiration_date.utcnow()).days)


def _ensure_timezone(timestamp: datetime | None) -> datetime | None:
    """Calculate days left until domain expires."""
    if timestamp is None:
        return None

    # If timezone info isn't provided by the Whois, assume UTC.
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)

    return timestamp


SENSORS: tuple[WhoisSensorEntityDescription, ...] = (
    WhoisSensorEntityDescription(
        key="admin",
        name="Admin",
        icon="mdi:account-star",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda domain: getattr(domain, "admin", None),
    ),
    WhoisSensorEntityDescription(
        key="creation_date",
        name="Created",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda domain: _ensure_timezone(domain.creation_date),
    ),
    WhoisSensorEntityDescription(
        key="days_until_expiration",
        name="Days Until Expiration",
        icon="mdi:calendar-clock",
        native_unit_of_measurement=TIME_DAYS,
        value_fn=_days_until_expiration,
    ),
    WhoisSensorEntityDescription(
        key="expiration_date",
        name="Expires",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda domain: _ensure_timezone(domain.expiration_date),
    ),
    WhoisSensorEntityDescription(
        key="last_updated",
        name="Last Updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda domain: _ensure_timezone(domain.last_updated),
    ),
    WhoisSensorEntityDescription(
        key="owner",
        name="Owner",
        icon="mdi:account",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda domain: getattr(domain, "owner", None),
    ),
    WhoisSensorEntityDescription(
        key="registrant",
        name="Registrant",
        icon="mdi:account-edit",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda domain: getattr(domain, "registrant", None),
    ),
    WhoisSensorEntityDescription(
        key="registrar",
        name="Registrar",
        icon="mdi:store",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda domain: domain.registrar if domain.registrar else None,
    ),
    WhoisSensorEntityDescription(
        key="reseller",
        name="Reseller",
        icon="mdi:store",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda domain: getattr(domain, "reseller", None),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WhoisSensorEntity(
                coordinator=coordinator,
                description=description,
                domain=entry.data[CONF_DOMAIN],
            )
            for description in SENSORS
        ],
    )


class WhoisSensorEntity(CoordinatorEntity, SensorEntity):
    """Implementation of a WHOIS sensor."""

    entity_description: WhoisSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: WhoisSensorEntityDescription,
        domain: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_name = f"{domain} {description.name}"
        self._attr_unique_id = f"{domain}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, domain)},
            entry_type=DeviceEntryType.SERVICE,
        )
        self._domain = domain

    @property
    def native_value(self) -> datetime | int | str | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, int | float | None] | None:
        """Return the state attributes of the monitored installation."""

        # Only add attributes to the original sensor
        if self.entity_description.key != "days_until_expiration":
            return None

        if self.coordinator.data is None:
            return None

        attrs = {}
        if expiration_date := self.coordinator.data.expiration_date:
            attrs[ATTR_EXPIRES] = expiration_date.isoformat()

        if name_servers := self.coordinator.data.name_servers:
            attrs[ATTR_NAME_SERVERS] = " ".join(name_servers)

        if last_updated := self.coordinator.data.last_updated:
            attrs[ATTR_UPDATED] = last_updated.isoformat()

        if registrar := self.coordinator.data.registrar:
            attrs[ATTR_REGISTRAR] = registrar

        if not attrs:
            return None

        return attrs
