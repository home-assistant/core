"""Support for iZone numbers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from operator import attrgetter
from typing import override

from pizone import Controller, Zone

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import IZoneConfigEntry, IZoneCoordinator
from .entity import IZoneCoordinatorEntity, zone_device_info

PARALLEL_UPDATES = 0

# pizone only accepts zone airflow limits in 5% steps.
AIRFLOW_STEP = 5


@dataclass(frozen=True, kw_only=True)
class IZoneZoneNumberEntityDescription(NumberEntityDescription):
    """Describes an iZone zone number backed by pizone airflow limits."""

    value_fn: Callable[[Zone], int]
    set_fn: Callable[[Zone, int], Awaitable[None]]
    locked_fn: Callable[[Controller], bool | None]


ZONE_NUMBER_DESCRIPTIONS: tuple[IZoneZoneNumberEntityDescription, ...] = (
    IZoneZoneNumberEntityDescription(
        key="damper_min",
        translation_key="damper_min",
        native_min_value=0,
        native_max_value=100,
        native_step=AIRFLOW_STEP,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        value_fn=attrgetter("airflow_min"),
        set_fn=lambda zone, value: zone.set_airflow_min(value),
        locked_fn=attrgetter("airflow_min_lock"),
    ),
    IZoneZoneNumberEntityDescription(
        key="damper_max",
        translation_key="damper_max",
        native_min_value=0,
        native_max_value=100,
        native_step=AIRFLOW_STEP,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        value_fn=attrgetter("airflow_max"),
        set_fn=lambda zone, value: zone.set_airflow_max(value),
        locked_fn=attrgetter("airflow_lock"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IZoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up iZone number entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        IZoneZoneNumber(coordinator, description, zone)
        for zone in coordinator.controller.zones
        for description in ZONE_NUMBER_DESCRIPTIONS
    )


class IZoneZoneNumber(IZoneCoordinatorEntity, NumberEntity):
    """Zone damper limit; unavailable while the installer airflow lock is on."""

    _attr_has_entity_name = True
    entity_description: IZoneZoneNumberEntityDescription

    def __init__(
        self,
        coordinator: IZoneCoordinator,
        description: IZoneZoneNumberEntityDescription,
        zone: Zone,
    ) -> None:
        """Initialize the number for *zone*."""
        super().__init__(coordinator)
        self.entity_description = description
        self._zone = zone
        self._attr_unique_id = (
            f"{coordinator.controller.device_uid}_z{zone.index + 1}_{description.key}"
        )
        self._attr_device_info = zone_device_info(coordinator, zone)

    @property
    @override
    def available(self) -> bool:
        """Also unavailable while the controller locks this airflow limit."""
        return super().available and not self.entity_description.locked_fn(
            self.controller
        )

    @property
    @override
    def native_value(self) -> int:
        """Return the zone airflow limit."""
        return self.entity_description.value_fn(self._zone)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the zone airflow limit."""
        # The number service only enforces min/max, not the step.
        if value % AIRFLOW_STEP:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_airflow_step",
                translation_placeholders={"value": f"{value:g}"},
            )
        await self._async_run_and_update(
            self.entity_description.set_fn(self._zone, int(value))
        )
