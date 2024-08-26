"""Creates the binary sensor entities for the mower."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import TYPE_CHECKING

from aioautomower.model import MowerActivities, MowerAttributes

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from . import AutomowerConfigEntry
from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity
from .util import entity_used_in

_LOGGER = logging.getLogger(__name__)


class AutomowerBinarySensorEntityTypes(StrEnum):
    """Automower Entities."""

    BATTERY_CHARGING = "battery_charging"
    LEAVING_DOCK = "leaving_dock"
    RETURNING_TO_DOCK = "returning_to_dock"


@dataclass(frozen=True, kw_only=True)
class AutomowerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Automower binary sensor entity."""

    value_fn: Callable[[MowerAttributes], bool]


BINARY_SENSOR_TYPES: tuple[AutomowerBinarySensorEntityDescription, ...] = (
    AutomowerBinarySensorEntityDescription(
        key=AutomowerBinarySensorEntityTypes.BATTERY_CHARGING,
        value_fn=lambda data: data.mower.activity == MowerActivities.CHARGING,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    AutomowerBinarySensorEntityDescription(
        key=AutomowerBinarySensorEntityTypes.LEAVING_DOCK,
        translation_key=AutomowerBinarySensorEntityTypes.LEAVING_DOCK,
        value_fn=lambda data: data.mower.activity == MowerActivities.LEAVING,
    ),
    AutomowerBinarySensorEntityDescription(
        key=AutomowerBinarySensorEntityTypes.RETURNING_TO_DOCK,
        translation_key=AutomowerBinarySensorEntityTypes.RETURNING_TO_DOCK,
        value_fn=lambda data: data.mower.activity == MowerActivities.GOING_HOME,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        AutomowerBinarySensorEntity(mower_id, coordinator, description)
        for mower_id in coordinator.data
        for description in BINARY_SENSOR_TYPES
    )


class AutomowerBinarySensorEntity(AutomowerBaseEntity, BinarySensorEntity):
    """Defining the Automower Sensors with AutomowerBinarySensorEntityDescription."""

    entity_description: AutomowerBinarySensorEntityDescription

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        description: AutomowerBinarySensorEntityDescription,
    ) -> None:
        """Set up AutomowerSensors."""
        super().__init__(mower_id, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.mower_attributes)

    async def async_added_to_hass(self) -> None:
        """Raise issue when entity is registered and was not disabled."""
        if TYPE_CHECKING:
            assert self.unique_id
        if entity_id := er.async_get(self.hass).async_get_entity_id(
            BINARY_SENSOR_DOMAIN, DOMAIN, self.unique_id
        ):
            if (
                self.enabled
                and self.entity_description.key
                in AutomowerBinarySensorEntityTypes.RETURNING_TO_DOCK
                and entity_used_in(self.hass, entity_id)
            ):
                async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"deprecated_task_entity_{self.entity_description.key}",
                    breaks_in_ha_version="2025.2.0",
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_task_entity",
                    translation_placeholders={
                        "task_name": str(self.name),
                        "entity": entity_id,
                    },
                )
            else:
                async_delete_issue(
                    self.hass,
                    DOMAIN,
                    f"deprecated_task_entity_{self.entity_description.key}",
                )
        await super().async_added_to_hass()
