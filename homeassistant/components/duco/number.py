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
        new_entities = []
        for zone_id in BYPASS_SUPPLY_TARGET_ZONE_IDS:
            if zone_id in known_zone_ids:
                continue

            target = coordinator.data.bypass_supply_temperature_targets.get(zone_id)
            if target is None:
                continue

            # Skip incomplete metadata because guessing valid limits would expose an invalid control.
            if (
                target.minimum is None
                or target.maximum is None
                or target.increment is None
            ):
                continue

            known_zone_ids.add(zone_id)
            new_entities.append(
                DucoBypassSupplyTemperatureTargetNumber(
                    coordinator,
                    coordinator.data.nodes[BOX_NODE_ID],
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

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: DucoCoordinator,
        node: Node,
        zone_id: int,
        minimum: float,
        maximum: float,
        increment: float,
    ) -> None:
        """Initialize the bypass supply temperature target number."""
        super().__init__(coordinator, node)
        self._zone_id = zone_id
        self._attr_translation_key = "bypass_supply_target_temperature_zone"
        self._attr_translation_placeholders = {"zone": str(zone_id)}
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
        if (
            (Decimal(str(value)) - Decimal(str(self.native_min_value)))
            / Decimal(str(self.native_step))
        ) % 1 != 0:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_bypass_supply_temperature_target_step",
                translation_placeholders={
                    "value": str(value),
                    "minimum": str(self.native_min_value),
                    "increment": str(self.native_step),
                },
            )

    def _normalize_step_value(self, value: float) -> float:
        """Normalize converted temperature values to the nearest supported native step."""
        if self.unit_of_measurement == self.native_unit_of_measurement:
            return value

        # Home Assistant converts service values from the configured temperature
        # unit first, which can land between valid Duco Celsius increments.
        steps = (
            (Decimal(str(value)) - Decimal(str(self.native_min_value)))
            / Decimal(str(self.native_step))
        ).to_integral_value(rounding=ROUND_HALF_UP)
        return float(
            Decimal(str(self.native_min_value))
            + (steps * Decimal(str(self.native_step)))
        )

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

        await self.coordinator.async_request_refresh()
