"""Support for Lektrico select entities."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from lektricowifi import Device

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import ATTR_SERIAL_NUMBER, CONF_TYPE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LektricoConfigEntry, LektricoDeviceDataUpdateCoordinator
from .entity import LektricoEntity


@dataclass(frozen=True, kw_only=True)
class LektricoSelectEntityDescription(SelectEntityDescription):
    """Describes Lektrico select entity."""

    value_fn: Callable[[dict[str, Any]], str]
    set_value_fn: Callable[[Device, int], Coroutine[Any, Any, dict[Any, Any]]]


LB_MODE_OPTIONS = [
    "disabled",
    "power",
    "hybrid",
    "green",
]


SELECTS: tuple[LektricoSelectEntityDescription, ...] = (
    LektricoSelectEntityDescription(
        key="load_balancing_mode",
        translation_key="load_balancing_mode",
        options=LB_MODE_OPTIONS,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: LB_MODE_OPTIONS[data["lb_mode"]],
        set_value_fn=lambda device, value: device.set_load_balancing_mode(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LektricoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lektrico select entities based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        LektricoSelect(
            description,
            coordinator,
            f"{entry.data[CONF_TYPE]}_{entry.data[ATTR_SERIAL_NUMBER]}",
        )
        for description in SELECTS
    )


class LektricoSelect(LektricoEntity, SelectEntity):
    """Defines a Lektrico select entity."""

    entity_description: LektricoSelectEntityDescription

    def __init__(
        self,
        description: LektricoSelectEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        device_name: str,
    ) -> None:
        """Initialize Lektrico select."""
        super().__init__(coordinator, device_name)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the state of the select."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.set_value_fn(
            self.coordinator.device, LB_MODE_OPTIONS.index(option)
        )
        await self.coordinator.async_request_refresh()
