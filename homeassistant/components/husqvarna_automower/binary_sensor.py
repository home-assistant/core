"""Creates the binary sensor entities for the mower."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from aioautomower.model import MowerActivities, MowerAttributes

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.script import scripts_with_entity
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

_LOGGER = logging.getLogger(__name__)
# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


def entity_used_in(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Get list of related automations and scripts."""
    used_in = automations_with_entity(hass, entity_id)
    used_in += scripts_with_entity(hass, entity_id)
    return used_in


@dataclass(frozen=True, kw_only=True)
class AutomowerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Automower binary sensor entity."""

    value_fn: Callable[[MowerAttributes], bool]


MOWER_BINARY_SENSOR_TYPES: tuple[AutomowerBinarySensorEntityDescription, ...] = (
    AutomowerBinarySensorEntityDescription(
        key="battery_charging",
        value_fn=lambda data: data.mower.activity == MowerActivities.CHARGING,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    AutomowerBinarySensorEntityDescription(
        key="leaving_dock",
        translation_key="leaving_dock",
        value_fn=lambda data: data.mower.activity == MowerActivities.LEAVING,
    ),
    AutomowerBinarySensorEntityDescription(
        key="returning_to_dock",
        translation_key="returning_to_dock",
        value_fn=lambda data: data.mower.activity == MowerActivities.GOING_HOME,
        entity_registry_enabled_default=False,
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
        for description in MOWER_BINARY_SENSOR_TYPES
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
        if not (
            entity_id := er.async_get(self.hass).async_get_entity_id(
                BINARY_SENSOR_DOMAIN, DOMAIN, self.unique_id
            )
        ):
            return
        if (
            self.enabled
            and self.entity_description.key == "returning_to_dock"
            and entity_used_in(self.hass, entity_id)
        ):
            async_create_issue(
                self.hass,
                DOMAIN,
                f"deprecated_entity_{self.entity_description.key}",
                breaks_in_ha_version="2025.6.0",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_entity",
                translation_placeholders={
                    "entity_name": str(self.name),
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
