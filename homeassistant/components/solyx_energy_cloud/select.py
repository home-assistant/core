"""Select entities for the Solyx Energy Cloud integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import callback

from .const import OPERATING_MODES
from .coordinator import SolyxEnergyConfigEntry, SolyxEnergyCoordinator, SolyxEnergyData
from .entity import SolyxNymoEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SolyxSelectEntityDescription(SelectEntityDescription):
    """Describes a Solyx Energy select entity."""

    value_fn: Callable[[SolyxEnergyData], str | None]
    select_fn: Callable[[SolyxEnergyCoordinator, str, str], Awaitable[None]]


SELECT_DESCRIPTIONS: tuple[SolyxSelectEntityDescription, ...] = (
    SolyxSelectEntityDescription(
        key="operating_mode",
        translation_key="operating_mode",
        options=[mode.lower() for mode in OPERATING_MODES],
        value_fn=lambda data: data.operating_mode,
        select_fn=lambda coordinator, device_id, option: (
            coordinator.async_set_operating_mode(device_id, option.upper())
        ),
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: SolyxEnergyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Solyx Energy selects from a config entry."""
    coordinator = entry.runtime_data
    known_devices: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        new_devices = set(coordinator.data) - known_devices
        if not new_devices:
            return

        known_devices.update(new_devices)
        async_add_entities(
            SolyxSelectEntity(coordinator, description, device_id)
            for device_id in sorted(new_devices)
            for description in SELECT_DESCRIPTIONS
        )

    _add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))


class SolyxSelectEntity(SolyxNymoEntity, SelectEntity):
    """A single Solyx Energy select entity."""

    entity_description: SolyxSelectEntityDescription

    @property
    @override
    def current_option(self) -> str | None:
        """Return the option last reported by the Solyx Energy cloud."""
        value = self.entity_description.value_fn(self.coordinator.data[self.device_id])
        return value.lower() if value is not None else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Push the selected option to the Solyx Energy cloud."""
        await self.entity_description.select_fn(
            self.coordinator, self.device_id, option
        )
