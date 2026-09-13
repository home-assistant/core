"""Vistapool Time entities."""

from dataclasses import dataclass
from datetime import time
from typing import override

from aioaquarite import AquariteError

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VistapoolConfigEntry
from .const import DOMAIN, SIGNAL_NEW_POOL
from .coordinator import VistapoolDataUpdateCoordinator
from .entity import VistapoolEntity

PARALLEL_UPDATES = 1

_SECONDS_PER_HOUR = 3600
_SECONDS_PER_MINUTE = 60


@dataclass(frozen=True, kw_only=True)
class VistapoolTimeEntityDescription(TimeEntityDescription):
    """Describes a Vistapool time entity."""

    value_path: str
    # A field the controller only reports when it supports the feature.
    presence_path: str | None = None


TIME_DESCRIPTIONS: tuple[VistapoolTimeEntityDescription, ...] = (
    *(
        VistapoolTimeEntityDescription(
            key=f"filtration_interval_{interval}_{bound}",
            translation_key=f"filtration_interval_{bound}",
            translation_placeholders={"number": str(interval)},
            entity_category=EntityCategory.CONFIG,
            value_path=f"filtration.interval{interval}.{api_field}",
        )
        for interval in (1, 2, 3)
        for bound, api_field in (("start", "from"), ("end", "to"))
    ),
    *(
        VistapoolTimeEntityDescription(
            key=f"light_schedule_{bound}",
            translation_key=f"light_schedule_{bound}",
            entity_category=EntityCategory.CONFIG,
            value_path=f"light.{api_field}",
            presence_path=f"light.{api_field}",
        )
        for bound, api_field in (("start", "from"), ("end", "to"))
    ),
)


def _build_time_entities(
    coordinator: VistapoolDataUpdateCoordinator,
) -> list[TimeEntity]:
    """Build the time entities for a single pool."""
    return [
        VistapoolTime(coordinator, description)
        for description in TIME_DESCRIPTIONS
        if description.presence_path is None
        or coordinator.get_value(description.presence_path) is not None
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VistapoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vistapool time entities for every pool on the account."""
    entities: list[TimeEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        entities.extend(_build_time_entities(coordinator))
    async_add_entities(entities)

    @callback
    def _async_add_pool(coordinator: VistapoolDataUpdateCoordinator) -> None:
        async_add_entities(_build_time_entities(coordinator))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_NEW_POOL}_{entry.entry_id}", _async_add_pool
        )
    )


class VistapoolTime(VistapoolEntity, TimeEntity):
    """Generic Vistapool time driven by an entity description."""

    entity_description: VistapoolTimeEntityDescription

    def __init__(
        self,
        coordinator: VistapoolDataUpdateCoordinator,
        description: VistapoolTimeEntityDescription,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self.build_unique_id(description.key)

    @property
    @override
    def native_value(self) -> time | None:
        """Return the interval bound as a time, decoded from seconds since midnight."""
        raw = self.coordinator.get_value(self.entity_description.value_path)
        if raw is None:
            return None
        try:
            seconds = int(raw)
            return time(
                seconds // _SECONDS_PER_HOUR,
                (seconds % _SECONDS_PER_HOUR) // _SECONDS_PER_MINUTE,
                seconds % _SECONDS_PER_MINUTE,
            )
        except TypeError, ValueError:
            # Also covers out-of-range values (negative or >= 24h), which make
            # the time() constructor raise instead of silently wrapping.
            return None

    @override
    async def async_set_value(self, value: time) -> None:
        """Send the interval bound to the controller as seconds since midnight."""
        seconds = (
            value.hour * _SECONDS_PER_HOUR
            + value.minute * _SECONDS_PER_MINUTE
            + value.second
        )
        try:
            await self.coordinator.api.set_value(
                self.coordinator.pool_id,
                self.entity_description.value_path,
                seconds,
            )
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={"entity": self.entity_id},
            ) from err
        self.coordinator.apply_optimistic(self.entity_description.value_path, seconds)
