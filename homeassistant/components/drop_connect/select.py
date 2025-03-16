"""Support for DROP selects."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DEVICE_TYPE, DEV_HUB
from .coordinator import DROPConfigEntry, DROPDeviceDataUpdateCoordinator
from .entity import DROPEntity

_LOGGER = logging.getLogger(__name__)

# Select type constants
PROTECT_MODE = "protect_mode"

PROTECT_MODE_OPTIONS = ["away", "home", "schedule"]


@dataclass(kw_only=True, frozen=True)
class DROPSelectEntityDescription(SelectEntityDescription):
    """Describes DROP select entity."""

    value_fn: Callable[[DROPDeviceDataUpdateCoordinator], int | None]
    set_fn: Callable[[DROPDeviceDataUpdateCoordinator, str], Awaitable[Any]]


SELECTS: list[DROPSelectEntityDescription] = [
    DROPSelectEntityDescription(
        key=PROTECT_MODE,
        translation_key=PROTECT_MODE,
        options=PROTECT_MODE_OPTIONS,
        value_fn=lambda device: device.drop_api.protect_mode(),
        set_fn=lambda device, value: device.set_protect_mode(value),
    )
]

# Defines which selects are used by each device type
DEVICE_SELECTS: dict[str, list[str]] = {
    DEV_HUB: [PROTECT_MODE],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DROPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DROP selects from config entry."""
    _LOGGER.debug(
        "Set up select for device type %s with entry_id is %s",
        config_entry.data[CONF_DEVICE_TYPE],
        config_entry.entry_id,
    )

    coordinator = config_entry.runtime_data
    if config_entry.data[CONF_DEVICE_TYPE] in DEVICE_SELECTS:
        async_add_entities(
            DROPSelect(coordinator, select)
            for select in SELECTS
            if select.key in DEVICE_SELECTS[config_entry.data[CONF_DEVICE_TYPE]]
        )


class DROPSelect(DROPEntity, SelectEntity):
    """Representation of a DROP select."""

    entity_description: DROPSelectEntityDescription

    def __init__(
        self,
        coordinator: DROPDeviceDataUpdateCoordinator,
        entity_description: DROPSelectEntityDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(entity_description.key, coordinator)
        self.entity_description = entity_description

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        val = self.entity_description.value_fn(self.coordinator)
        return str(val) if val else None

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        await self.entity_description.set_fn(self.coordinator, option)
