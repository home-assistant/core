"""Platform for number."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from ohme import ApiException, OhmeApiClient

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import OhmeConfigEntry
from .entity import OhmeEntity, OhmeEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class OhmeNumberDescription(OhmeEntityDescription, NumberEntityDescription):
    """Class describing Ohme number entities."""

    set_fn: Callable[[OhmeApiClient, float], Coroutine[Any, Any, bool]]
    value_fn: Callable[[OhmeApiClient], float]


NUMBER_DESCRIPTION = [
    OhmeNumberDescription(
        key="target_percentage",
        translation_key="target_percentage",
        value_fn=lambda client: client.target_soc,
        set_fn=lambda client, value: client.async_set_target(target_percent=int(value)),
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    OhmeNumberDescription(
        key="preconditioning_duration",
        translation_key="preconditioning_duration",
        value_fn=lambda client: client.preconditioning,
        set_fn=lambda client, value: client.async_set_target(
            pre_condition_length=int(value)
        ),
        native_min_value=0,
        native_max_value=60,
        native_step=5,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up numbers."""
    coordinators = config_entry.runtime_data
    coordinator = coordinators.charge_session_coordinator

    async_add_entities(
        OhmeNumber(coordinator, description)
        for description in NUMBER_DESCRIPTION
        if description.is_supported_fn(coordinator.client)
    )


class OhmeNumber(OhmeEntity, NumberEntity):
    """Generic number entity for Ohme."""

    entity_description: OhmeNumberDescription

    @property
    def native_value(self) -> float:
        """Return the current value of the number."""
        return self.entity_description.value_fn(self.coordinator.client)

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        try:
            await self.entity_description.set_fn(self.coordinator.client, value)
        except ApiException as e:
            raise HomeAssistantError(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from e
        await self.coordinator.async_request_refresh()
