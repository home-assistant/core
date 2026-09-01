"""Number platform for the Duco integration."""

import logging
from typing import override

from duco_connectivity import DucoError, DucoRateLimitError
from duco_connectivity.models import Node

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BOX_NODE_ID, DOMAIN
from .coordinator import DucoConfigEntry, DucoCoordinator
from .entity import DucoEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


NUMBER_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="bypass_supply_target_temperature_zone",
        translation_key="bypass_supply_target_temperature_zone",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DucoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duco number entities."""
    coordinator = entry.runtime_data
    known_entities: set[tuple[str, int]] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add number entities for discovered bypass temperature targets."""
        new_entities = []
        targets = coordinator.data.bypass_supply_temperature_targets
        for description in NUMBER_DESCRIPTIONS:
            for zone_id, target in targets.items():
                if (description.key, zone_id) in known_entities:
                    continue

                known_entities.add((description.key, zone_id))
                new_entities.append(
                    DucoBypassSupplyTemperatureTargetNumber(
                        coordinator,
                        coordinator.data.nodes[BOX_NODE_ID],
                        description,
                        zone_id,
                        target.minimum,
                        target.maximum,
                        target.increment,
                    )
                )

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))
    _async_add_new_entities()


class DucoBypassSupplyTemperatureTargetNumber(DucoEntity, NumberEntity):
    """Number entity for a zone's bypass supply temperature target."""

    def __init__(
        self,
        coordinator: DucoCoordinator,
        node: Node,
        description: NumberEntityDescription,
        zone_id: int,
        minimum: float,
        maximum: float,
        increment: float,
    ) -> None:
        """Initialize the bypass supply temperature target number."""
        super().__init__(coordinator, node)
        self.entity_description = description
        self._zone_id = zone_id
        self._attr_translation_placeholders = {"zone": str(zone_id)}
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{node.node_id}_"
            f"{description.key}_{zone_id}"
        )
        # Duco reports these as capability bounds for the target control rather
        # than live state, so the number entity keeps them fixed after creation.
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = increment

    @property
    @override
    def available(self) -> bool:
        """Return True if the zone currently exposes a bypass target."""
        return (
            super().available
            and self._zone_id in self.coordinator.data.bypass_supply_temperature_targets
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current bypass supply temperature target."""
        target = self.coordinator.data.bypass_supply_temperature_targets.get(
            self._zone_id
        )
        return target.value if target else None

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the bypass supply temperature target."""
        target = self.coordinator.data.bypass_supply_temperature_targets[self._zone_id]

        try:
            if self.unit_of_measurement != self.native_unit_of_measurement:
                value = target.normalize_value(value)
            await self.coordinator.client.async_set_bypass_supply_temperature_target(
                self._zone_id, value, target=target
            )
        except ValueError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_bypass_supply_temperature_target_step",
                translation_placeholders={
                    "value": str(value),
                    "minimum": str(self.native_min_value),
                    "increment": str(self.native_step),
                },
            ) from err
        except DucoRateLimitError as err:
            _LOGGER.warning(
                "Duco write rate limit exceeded for bypass target zone %s",
                self._zone_id,
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rate_limit_exceeded",
            ) from err
        except DucoError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_set_bypass_supply_temperature_target",
            ) from err

        await self.coordinator.async_request_refresh()
