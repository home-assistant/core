"""Support for Elgato select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from elgato import Elgato, PowerOnBehavior

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElgatoConfigEntry, ElgatoData, ElgatoDataUpdateCoordinator
from .entity import ElgatoEntity
from .helpers import elgato_device_action

PARALLEL_UPDATES = 1

# The device also has a value 0, which it reports when it has no opinion yet.
# It cannot be selected, so it is not an option, and it leaves the entity
# unknown until the behavior is actually set.
POWER_ON_BEHAVIORS = {
    PowerOnBehavior.RESTORE_LAST: "restore_last",
    PowerOnBehavior.USE_DEFAULTS: "use_defaults",
}
POWER_ON_BEHAVIOR_OPTIONS = {value: key for key, value in POWER_ON_BEHAVIORS.items()}


@dataclass(frozen=True, kw_only=True)
class ElgatoSelectEntityDescription(SelectEntityDescription):
    """Class describing Elgato select entities."""

    has_fn: Callable[[ElgatoData], bool] = lambda _: True
    current_fn: Callable[[ElgatoData], str | None]
    select_fn: Callable[[Elgato, str], Awaitable[Any]]


SELECTS = [
    ElgatoSelectEntityDescription(
        key="power_on_behavior",
        translation_key="power_on_behavior",
        entity_category=EntityCategory.CONFIG,
        options=list(POWER_ON_BEHAVIORS.values()),
        current_fn=lambda x: POWER_ON_BEHAVIORS.get(x.settings.power_on_behavior),
        select_fn=lambda client, option: client.power_on_behavior(
            behavior=POWER_ON_BEHAVIOR_OPTIONS[option]
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElgatoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elgato select entities based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        ElgatoSelectEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in SELECTS
        if description.has_fn(coordinator.data)
    )


class ElgatoSelectEntity(ElgatoEntity, SelectEntity):
    """Representation of an Elgato select entity."""

    entity_description: ElgatoSelectEntityDescription

    def __init__(
        self,
        coordinator: ElgatoDataUpdateCoordinator,
        description: ElgatoSelectEntityDescription,
    ) -> None:
        """Initiate Elgato select entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.data.info.serial_number}_{description.key}"
        )

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected option."""
        return self.entity_description.current_fn(self.coordinator.data)

    @elgato_device_action
    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.coordinator.client, option)
