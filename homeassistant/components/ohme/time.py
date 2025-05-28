"""Platform for time."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import time
from typing import Any

from ohme import ApiException, OhmeApiClient

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import OhmeConfigEntry
from .entity import OhmeEntity, OhmeEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class OhmeTimeDescription(OhmeEntityDescription, TimeEntityDescription):
    """Class describing Ohme time entities."""

    set_fn: Callable[[OhmeApiClient, time], Coroutine[Any, Any, bool]]
    value_fn: Callable[[OhmeApiClient], time]


TIME_DESCRIPTION = [
    OhmeTimeDescription(
        key="target_time",
        translation_key="target_time",
        value_fn=lambda client: time(
            hour=client.target_time[0], minute=client.target_time[1]
        ),
        set_fn=lambda client, value: client.async_set_target(
            target_time=(value.hour, value.minute)
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up time entities."""
    coordinators = config_entry.runtime_data
    coordinator = coordinators.charge_session_coordinator

    async_add_entities(
        OhmeTime(coordinator, description)
        for description in TIME_DESCRIPTION
        if description.is_supported_fn(coordinator.client)
    )


class OhmeTime(OhmeEntity, TimeEntity):
    """Generic time entity for Ohme."""

    entity_description: OhmeTimeDescription

    @property
    def native_value(self) -> time:
        """Return the current value of the time."""
        return self.entity_description.value_fn(self.coordinator.client)

    async def async_set_value(self, value: time) -> None:
        """Set the time value."""
        try:
            await self.entity_description.set_fn(self.coordinator.client, value)
        except ApiException as e:
            raise HomeAssistantError(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from e
        await self.coordinator.async_request_refresh()
