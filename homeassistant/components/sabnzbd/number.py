"""Number entities for the SABnzbd integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pysabnzbd import SabnzbdApiException

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SabnzbdConfigEntry, SabnzbdUpdateCoordinator
from .entity import SabnzbdEntity


@dataclass(frozen=True, kw_only=True)
class SabnzbdNumberEntityDescription(NumberEntityDescription):
    """Class describing a SABnzbd number entities."""

    set_fn: Callable[[SabnzbdUpdateCoordinator, float], Awaitable]


NUMBER_DESCRIPTIONS: tuple[SabnzbdNumberEntityDescription, ...] = (
    SabnzbdNumberEntityDescription(
        key="speedlimit",
        translation_key="speedlimit",
        mode=NumberMode.BOX,
        native_max_value=100,
        native_min_value=0,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        set_fn=lambda coordinator, speed: (
            coordinator.sab_api.set_speed_limit(int(speed))
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SabnzbdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SABnzbd number entity."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        SabnzbdNumber(coordinator, description) for description in NUMBER_DESCRIPTIONS
    )


class SabnzbdNumber(SabnzbdEntity, NumberEntity):
    """Representation of a SABnzbd number."""

    entity_description: SabnzbdNumberEntityDescription

    @property
    def native_value(self) -> float:
        """Return latest value for number."""
        return self.coordinator.data[self.entity_description.key]

    async def async_set_native_value(self, value: float) -> None:
        """Set the new number value."""
        try:
            await self.entity_description.set_fn(self.coordinator, value)
        except SabnzbdApiException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e
        else:
            await self.coordinator.async_request_refresh()
