"""Support for Škoda switches."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from skoda_public_api.api_layer.open_api_client import OpenAPIClient
from skoda_public_api.models.enums import ChargingState, VehicleCapability

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SkodaConfigEntry, SkodaUpdateCoordinator
from .entity import SkodaEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SkodaSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Škoda switch entity."""

    is_on_fn: Callable[[SkodaEntity], bool | None]
    turn_on_fn: Callable[[OpenAPIClient, str], Awaitable[Any]]
    turn_off_fn: Callable[[OpenAPIClient, str], Awaitable[Any]]
    required_capabilities: frozenset[VehicleCapability]


def _charging_is_on(entity: SkodaEntity) -> bool | None:
    charging = entity.open_api_charging
    if charging is None or charging.status is None or charging.status.state is None:
        return None
    return charging.status.state == ChargingState.CHARGING


SWITCH_TYPES: tuple[SkodaSwitchEntityDescription, ...] = (
    SkodaSwitchEntityDescription(
        key="charging",
        translation_key="charging",
        required_capabilities=frozenset({VehicleCapability.CHARGING}),
        is_on_fn=_charging_is_on,
        turn_on_fn=lambda client, vin: client.start_charging(vin),
        turn_off_fn=lambda client, vin: client.stop_charging(vin),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Škoda switches from a config entry."""
    coordinator = entry.runtime_data.coordinator
    capabilities = coordinator.data.vehicle_response.supported_capabilities()

    async_add_entities(
        SkodaSwitch(coordinator, description)
        for description in SWITCH_TYPES
        if description.required_capabilities <= capabilities
    )


class SkodaSwitch(SkodaEntity, SwitchEntity):
    """Škoda switch entity, driven by its entity description."""

    entity_description: SkodaSwitchEntityDescription

    def __init__(
        self,
        coordinator: SkodaUpdateCoordinator,
        description: SkodaSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        self.entity_description = description
        super().__init__(coordinator, coordinator.vin)
        self._assumed_is_on: bool | None = None

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        if self._assumed_is_on is not None:
            return self._assumed_is_on
        return self.entity_description.is_on_fn(self)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self._assumed_is_on = None
        super()._handle_coordinator_update()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.async_send_command(self.entity_description.turn_on_fn)
        self._set_assumed_state(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.async_send_command(self.entity_description.turn_off_fn)
        self._set_assumed_state(False)

    def _set_assumed_state(self, is_on: bool) -> None:
        # The vehicle reports the new state with a delay, and an immediate refresh
        # would spend the small per-VIN request budget, so keep the requested state
        # until the next scheduled update.
        self._assumed_is_on = is_on
        self.async_write_ha_state()
