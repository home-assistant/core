"""Support for TechnoVE binary sensor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from technove import Station as TechnoVEStation

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from . import TechnoVEConfigEntry
from .const import DOMAIN
from .coordinator import TechnoVEDataUpdateCoordinator
from .entity import TechnoVEEntity


@dataclass(frozen=True, kw_only=True)
class TechnoVEBinarySensorDescription(BinarySensorEntityDescription):
    """Describes TechnoVE binary sensor entity."""

    deprecated_version: str | None = None
    value_fn: Callable[[TechnoVEStation], bool | None]


BINARY_SENSORS = [
    TechnoVEBinarySensorDescription(
        key="conflict_in_sharing_config",
        translation_key="conflict_in_sharing_config",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda station: station.info.conflict_in_sharing_config,
    ),
    TechnoVEBinarySensorDescription(
        key="in_sharing_mode",
        translation_key="in_sharing_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda station: station.info.in_sharing_mode,
    ),
    TechnoVEBinarySensorDescription(
        key="is_battery_protected",
        translation_key="is_battery_protected",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda station: station.info.is_battery_protected,
    ),
    TechnoVEBinarySensorDescription(
        key="is_session_active",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda station: station.info.is_session_active,
        deprecated_version="2025.2.0",
        # Disabled by default, as this entity is deprecated
        entity_registry_enabled_default=False,
    ),
    TechnoVEBinarySensorDescription(
        key="is_static_ip",
        translation_key="is_static_ip",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda station: station.info.is_static_ip,
    ),
    TechnoVEBinarySensorDescription(
        key="update_available",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.UPDATE,
        value_fn=lambda station: not station.info.is_up_to_date,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TechnoVEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    async_add_entities(
        TechnoVEBinarySensorEntity(entry.runtime_data, description)
        for description in BINARY_SENSORS
    )


class TechnoVEBinarySensorEntity(TechnoVEEntity, BinarySensorEntity):
    """Defines a TechnoVE binary sensor entity."""

    entity_description: TechnoVEBinarySensorDescription

    def __init__(
        self,
        coordinator: TechnoVEDataUpdateCoordinator,
        description: TechnoVEBinarySensorDescription,
    ) -> None:
        """Initialize a TechnoVE binary sensor entity."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""

        return self.entity_description.value_fn(self.coordinator.data)

    async def async_added_to_hass(self) -> None:
        """Raise issue when entity is registered and was not disabled."""
        if TYPE_CHECKING:
            assert self.unique_id
        if entity_id := er.async_get(self.hass).async_get_entity_id(
            BINARY_SENSOR_DOMAIN, DOMAIN, self.unique_id
        ):
            if self.enabled and self.entity_description.deprecated_version:
                async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"deprecated_entity_{self.entity_description.key}",
                    breaks_in_ha_version=self.entity_description.deprecated_version,
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key=f"deprecated_entity_{self.entity_description.key}",
                    translation_placeholders={
                        "sensor_name": self.name
                        if isinstance(self.name, str)
                        else entity_id,
                        "entity": entity_id,
                    },
                )
            else:
                async_delete_issue(
                    self.hass,
                    DOMAIN,
                    f"deprecated_entity_{self.entity_description.key}",
                )
        await super().async_added_to_hass()
