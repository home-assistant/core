"""Imeon inverter select support."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_INVERTER_MODE
from .coordinator import Inverter, InverterCoordinator
from .entity import InverterEntity

type InverterConfigEntry = ConfigEntry[InverterCoordinator]

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ImeonSelectEntityDescription(SelectEntityDescription):
    """Class to describe an Imeon inverter select entity."""

    set_value_fn: Callable[[Inverter, str], Awaitable[bool]]


SELECT_DESCRIPTIONS: tuple[ImeonSelectEntityDescription, ...] = (
    ImeonSelectEntityDescription(
        key="manager_inverter_mode",
        translation_key="manager_inverter_mode",
        options=ATTR_INVERTER_MODE,
        set_value_fn=lambda api, mode: api.set_inverter_mode(mode),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InverterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create each select for a given config entry."""

    coordinator = entry.runtime_data
    async_add_entities(
        InverterSelect(coordinator, entry, description)
        for description in SELECT_DESCRIPTIONS
    )


class InverterSelect(InverterEntity, SelectEntity):
    """Representation of an Imeon inverter select."""

    entity_description: ImeonSelectEntityDescription
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def current_option(self) -> str | None:
        """Return the state of the select."""
        value = self.coordinator.data.get(self.data_key)
        return str(value) if value is not None else None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.set_value_fn(self.coordinator.api, option)
