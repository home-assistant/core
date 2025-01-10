"""Get WHOIS information for a given host."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import ATTR_EXPIRES, ATTR_NAME_SERVERS, ATTR_REGISTRAR, ATTR_UPDATED, DOMAIN


@dataclass(frozen=True, kw_only=True)
class WhoisSensorEntityDescription(SensorEntityDescription):
    """Describes a Whois sensor entity."""

    value_fn: Callable[[dict[str, Any]], datetime | int | str | None]


def _days_until_expiration(data: dict[str, Any]) -> int | None:
    """Calculate days left until domain expires."""
    expiration_date = _get_single_value(data, "expiration_date")
    if expiration_date is None:
        return None
    # We need to cast here, as (unlike Pyright) mypy isn't able to determine the type.
    return cast(
        int,
        (expiration_date - dt_util.utcnow().replace(tzinfo=None)).days,
    )


def _ensure_timezone(timestamp: datetime | None) -> datetime | None:
    """Calculate days left until domain expires."""
    if timestamp is None:
        return None

    # If timezone info isn't provided by the Whois, assume UTC.
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)

    return timestamp


def _get_single_value(data: dict[str, Any], name: str) -> Any:
    """Retrieve and normalize generic single-value attributes from the external whois library."""
    value = data.get(name)
    if value is None:
        return None
    return value[0] if isinstance(value, list) else value


def _get_date(data: dict[str, Any], name: str) -> Any:
    """Retrieve and normalize generic date attributes from the external whois library."""
    value = _get_single_value(data, name)
    return value if isinstance(value, datetime) else None


def _get_owner(data: dict[str, Any]) -> str | None:
    """Retrieve and normalize owner information."""
    owner = (
        _get_single_value(data, "name")
        or _get_single_value(data, "org")
        or _get_single_value(data, "registrant_name")
    )
    return str(owner) if owner else None


def _get_name_servers(data: dict[str, Any]) -> list[str] | None:
    """Retrieve and normalize name_servers attribute from the external library."""
    name_servers = data.get("name_servers")
    if name_servers is None:
        return None
    ns = name_servers if isinstance(name_servers, list) else [name_servers]
    return [str(n).lower() for n in ns]


SENSORS: tuple[WhoisSensorEntityDescription, ...] = (
    WhoisSensorEntityDescription(
        key="admin",
        translation_key="admin",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_single_value(data, "admin"),
    ),
    WhoisSensorEntityDescription(
        key="creation_date",
        translation_key="creation_date",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _ensure_timezone(_get_date(data, "creation_date")),
    ),
    WhoisSensorEntityDescription(
        key="days_until_expiration",
        translation_key="days_until_expiration",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=_days_until_expiration,
    ),
    WhoisSensorEntityDescription(
        key="expiration_date",
        translation_key="expiration_date",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _ensure_timezone(_get_date(data, "expiration_date")),
    ),
    WhoisSensorEntityDescription(
        key="last_updated",
        translation_key="last_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _ensure_timezone(_get_date(data, "updated_date")),
    ),
    WhoisSensorEntityDescription(
        key="owner",
        translation_key="owner",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_get_owner,
    ),
    WhoisSensorEntityDescription(
        key="registrant",
        translation_key="registrant",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_single_value(data, "registrant"),
    ),
    WhoisSensorEntityDescription(
        key="registrar",
        translation_key="registrar",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_single_value(data, "registrar"),
    ),
    WhoisSensorEntityDescription(
        key="reseller",
        translation_key="reseller",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_single_value(data, "reseller"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""
    coordinator: DataUpdateCoordinator[dict[str, Any] | None] = hass.data[DOMAIN][
        entry.entry_id
    ]
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


class WhoisSensorEntity(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, Any] | None]], SensorEntity
):
    """Implementation of a WHOIS sensor."""

    entity_description: WhoisSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any] | None],
        description: WhoisSensorEntityDescription,
        domain: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{domain}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, domain)},
            name=domain,
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
        if expiration_date := _get_date(self.coordinator.data, "expiration_date"):
            attrs[ATTR_EXPIRES] = expiration_date.isoformat()

        if name_servers := _get_name_servers(self.coordinator.data):
            attrs[ATTR_NAME_SERVERS] = " ".join(name_servers)

        if last_updated := _get_date(self.coordinator.data, "updated_date"):
            attrs[ATTR_UPDATED] = last_updated.isoformat()

        if registrar := _get_single_value(self.coordinator.data, "registrar"):
            attrs[ATTR_REGISTRAR] = registrar

        if not attrs:
            return None

        return attrs
