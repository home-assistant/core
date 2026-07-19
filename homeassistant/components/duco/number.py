"""Number platform for the Duco integration."""

from decimal import ROUND_HALF_UP, Decimal
import logging
from typing import override

from duco_connectivity import DucoError, DucoRateLimitError
from duco_connectivity.models import Node

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BOX_NODE_ID, BYPASS_SUPPLY_TARGET_ZONE_IDS, DOMAIN
from .coordinator import DucoConfigEntry, DucoCoordinator
from .entity import DucoEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

_ZONE_TRANSLATION_KEYS = {
    1: "bypass_supply_target_temperature_zone_1",
    2: "bypass_supply_target_temperature_zone_2",
    3: "bypass_supply_target_temperature_zone_3",
    4: "bypass_supply_target_temperature_zone_4",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DucoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duco number entities."""
    coordinator = entry.runtime_data
    known_zone_ids: set[int] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add number entities for discovered bypass temperature targets."""
        box_node = coordinator.data.nodes.get(BOX_NODE_ID)
        if box_node is None:
            return

        new_entities = []
        for zone_id in BYPASS_SUPPLY_TARGET_ZONE_IDS:
            if zone_id in known_zone_ids:
                continue

            target = coordinator.data.bypass_supply_temperature_targets.get(zone_id)
            if target is None:
                continue

            minimum = target.minimum
            maximum = target.maximum
            increment = target.increment
            # Skip incomplete metadata because guessing valid limits would expose an invalid control.
            if minimum is None or maximum is None or increment is None:
                continue

            known_zone_ids.add(zone_id)
            new_entities.append(
                DucoBypassSupplyTemperatureTargetNumber(
                    coordinator,
                    box_node,
                    zone_id,
                    _ZONE_TRANSLATION_KEYS[zone_id],
                    minimum,
                    maximum,
                    increment,
                )
            )

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))
    _async_add_new_entities()


class DucoBypassSupplyTemperatureTargetNumber(DucoEntity, NumberEntity):
    """Number entity for a zone's bypass supply temperature target."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: DucoCoordinator,
        node: Node,
        zone_id: int,
        translation_key: str,
        minimum: float,
        maximum: float,
        increment: float,
    ) -> None:
        """Initialize the bypass supply temperature target number."""
        super().__init__(coordinator, node)
        self._zone_id = zone_id
        self._attr_translation_key = translation_key
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{node.node_id}_"
            f"bypass_supply_target_temperature_zone_{zone_id}"
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

    def _validate_step(self, value: float) -> None:
        """Validate the value follows the API-provided increment metadata."""
        minimum = self.native_min_value
        increment = self.native_step

        decimal_value = Decimal(str(value))
        decimal_minimum = Decimal(str(minimum))
        decimal_increment = Decimal(str(increment))

        if ((decimal_value - decimal_minimum) / decimal_increment) % 1 != 0:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_bypass_supply_temperature_target_step",
                translation_placeholders={
                    "value": str(value),
                    "minimum": str(minimum),
                    "increment": str(increment),
                },
            )

    def _normalize_step_value(self, value: float) -> float:
        """Normalize converted temperature values to the nearest supported native step."""
        if self.unit_of_measurement == self.native_unit_of_measurement:
            return value

        decimal_minimum = Decimal(str(self.native_min_value))
        decimal_increment = Decimal(str(self.native_step))
        decimal_value = Decimal(str(value))

        # Home Assistant converts service values from the configured temperature
        # unit first, which can land between valid Duco Celsius increments.
        steps = (
            (decimal_value - decimal_minimum) / decimal_increment
        ).to_integral_value(rounding=ROUND_HALF_UP)
        return float(decimal_minimum + (steps * decimal_increment))

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the bypass supply temperature target."""
        value = self._normalize_step_value(value)
        self._validate_step(value)

        try:
            await self.coordinator.client.async_set_bypass_supply_temperature_target(
                self._zone_id, value
            )
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

        await self.coordinator.async_refresh()
