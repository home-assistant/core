"""Vistapool Select entities."""

from dataclasses import dataclass
from typing import Any

from aioaquarite import AquariteError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VistapoolConfigEntry
from .const import DOMAIN
from .coordinator import VistapoolDataUpdateCoordinator
from .entity import VistapoolEntity

PARALLEL_UPDATES = 1

_PUMP_MODE_OPTIONS = ["manual", "auto", "heat", "smart", "intel"]
_PUMP_SPEED_OPTIONS = ["slow", "medium", "high"]


@dataclass(frozen=True, kw_only=True)
class VistapoolSelectEntityDescription(SelectEntityDescription):
    """Describes a Vistapool select entity."""

    value_path: str
    exists_path: str | tuple[str, ...] | None = None
    translation_placeholders: dict[str, str] | None = None


SELECT_DESCRIPTIONS: tuple[VistapoolSelectEntityDescription, ...] = (
    VistapoolSelectEntityDescription(
        key="pump_mode",
        translation_key="pump_mode",
        entity_category=EntityCategory.CONFIG,
        options=_PUMP_MODE_OPTIONS,
        value_path="filtration.mode",
    ),
    VistapoolSelectEntityDescription(
        key="pump_speed",
        translation_key="pump_speed",
        entity_category=EntityCategory.CONFIG,
        options=_PUMP_SPEED_OPTIONS,
        value_path="filtration.manVel",
    ),
    *(
        VistapoolSelectEntityDescription(
            key=f"filtration_timer_speed_{i}",
            translation_key="filtration_timer_speed",
            translation_placeholders={"number": str(i)},
            entity_category=EntityCategory.CONFIG,
            options=_PUMP_SPEED_OPTIONS,
            value_path=f"filtration.timerVel{i}",
        )
        for i in (1, 2, 3)
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VistapoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vistapool select entities for every pool on the account."""
    entities: list[SelectEntity] = []

    for coordinator in entry.runtime_data.coordinators.values():
        for description in SELECT_DESCRIPTIONS:
            if description.exists_path is not None:
                required = (
                    (description.exists_path,)
                    if isinstance(description.exists_path, str)
                    else description.exists_path
                )
                if not all(coordinator.get_value(path) for path in required):
                    continue
            entities.append(VistapoolSelect(coordinator, description))

    async_add_entities(entities)


def _to_index(raw: Any) -> int | None:
    """Convert a coordinator value into an options-list index, or None if not possible."""
    if raw is None:
        return None
    try:
        return int(raw)
    except TypeError, ValueError:
        return None


class VistapoolSelect(VistapoolEntity, SelectEntity):
    """Generic Vistapool select driven by an entity description."""

    entity_description: VistapoolSelectEntityDescription

    def __init__(
        self,
        coordinator: VistapoolDataUpdateCoordinator,
        description: VistapoolSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self.build_unique_id(description.key)
        if description.translation_placeholders is not None:
            self._attr_translation_placeholders = description.translation_placeholders

    @property
    def current_option(self) -> str | None:
        """Return the option that maps to the current API value."""
        index = _to_index(
            self.coordinator.get_value(self.entity_description.value_path)
        )
        options = self.entity_description.options or []
        if index is None or not 0 <= index < len(options):
            return None
        return options[index]

    async def async_select_option(self, option: str) -> None:
        """Send the index of the chosen option to the controller."""
        assert self.entity_description.options is not None
        index = self.entity_description.options.index(option)
        try:
            await self.coordinator.api.set_value(
                self.coordinator.pool_id,
                self.entity_description.value_path,
                index,
            )
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={"entity": self.entity_id},
            ) from err
