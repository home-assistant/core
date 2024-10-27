"""Creates the number entities for the mower."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from aioautomower.model import MowerAttributes, WorkArea
from aioautomower.session import AutomowerSession

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AutomowerConfigEntry
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import (
    AutomowerControlEntity,
    WorkAreaControlEntity,
    _work_area_translation_key,
    handle_sending_exception,
)

_LOGGER = logging.getLogger(__name__)


@callback
def _async_get_cutting_height(data: MowerAttributes) -> int:
    """Return the cutting height."""
    if TYPE_CHECKING:
        # Sensor does not get created if it is None
        assert data.settings.cutting_height is not None
    return data.settings.cutting_height


async def async_set_work_area_cutting_height(
    coordinator: AutomowerDataUpdateCoordinator,
    mower_id: str,
    cheight: float,
    work_area_id: int,
) -> None:
    """Set cutting height for work area."""
    await coordinator.api.commands.workarea_settings(
        mower_id, int(cheight), work_area_id
    )


async def async_set_cutting_height(
    session: AutomowerSession,
    mower_id: str,
    cheight: float,
) -> None:
    """Set cutting height."""
    await session.commands.set_cutting_height(mower_id, int(cheight))


@dataclass(frozen=True, kw_only=True)
class AutomowerNumberEntityDescription(NumberEntityDescription):
    """Describes Automower number entity."""

    exists_fn: Callable[[MowerAttributes], bool] = lambda _: True
    value_fn: Callable[[MowerAttributes], int]
    set_value_fn: Callable[[AutomowerSession, str, float], Awaitable[Any]]


MOWER_NUMBER_TYPES: tuple[AutomowerNumberEntityDescription, ...] = (
    AutomowerNumberEntityDescription(
        key="cutting_height",
        translation_key="cutting_height",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        native_min_value=1,
        native_max_value=9,
        exists_fn=lambda data: data.settings.cutting_height is not None,
        value_fn=_async_get_cutting_height,
        set_value_fn=async_set_cutting_height,
    ),
)


@dataclass(frozen=True, kw_only=True)
class WorkAreaNumberEntityDescription(NumberEntityDescription):
    """Describes Automower work area number entity."""

    value_fn: Callable[[WorkArea], int]
    translation_key_fn: Callable[[int, str], str]
    set_value_fn: Callable[
        [AutomowerDataUpdateCoordinator, str, float, int], Awaitable[Any]
    ]


WORK_AREA_NUMBER_TYPES: tuple[WorkAreaNumberEntityDescription, ...] = (
    WorkAreaNumberEntityDescription(
        key="cutting_height_work_area",
        translation_key_fn=_work_area_translation_key,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.cutting_height,
        set_value_fn=async_set_work_area_cutting_height,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number platform."""
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = []
    current_work_areas: dict[str, set[int]] = {}

    def _create_work_area_entities(
        mower_id: str, work_areas: list[int]
    ) -> list[NumberEntity]:
        """Create WorkAreaNumberEntity instances for the specified work areas."""
        return [
            WorkAreaNumberEntity(mower_id, coordinator, description, work_area_id)
            for description in WORK_AREA_NUMBER_TYPES
            for work_area_id in work_areas
        ]

    def _create_mower_entities(mower_id: str) -> list[NumberEntity]:
        """Create AutomowerNumberEntity instances for the specified mower."""
        return [
            AutomowerNumberEntity(mower_id, coordinator, description)
            for description in MOWER_NUMBER_TYPES
            if description.exists_fn(coordinator.data[mower_id])
        ]

    for mower_id in coordinator.data:
        if coordinator.data[mower_id].capabilities.work_areas:
            _work_areas = coordinator.data[mower_id].work_areas
            if _work_areas is not None:
                entities.extend(
                    _create_work_area_entities(mower_id, list(_work_areas.keys()))
                )
                current_work_areas[mower_id] = set(_work_areas.keys())

        entities.extend(_create_mower_entities(mower_id))

    async_add_entities(entities)

    def _remove_all_work_areas(removed_work_areas: set[int], mower_id: str) -> None:
        """Remove all unused work areas for all platforms."""
        entity_reg = er.async_get(hass)
        for entity_entry in er.async_entries_for_config_entry(
            entity_reg, entry.entry_id
        ):
            for work_area_id in removed_work_areas:
                if entity_entry.unique_id.startswith(f"{mower_id}_{work_area_id}_"):
                    _LOGGER.info("Deleting: %s", entity_entry.entity_id)
                    entity_reg.async_remove(entity_entry.entity_id)

    def _async_work_area_listener() -> None:
        """Listen for new work areas and add/remove number entities if they did not exist."""
        for mower_id in coordinator.data:
            if (
                coordinator.data[mower_id].capabilities.work_areas
                and (_work_areas := coordinator.data[mower_id].work_areas) is not None
            ):
                received_work_areas = set(_work_areas.keys())
                new_work_areas = received_work_areas - current_work_areas.get(
                    mower_id, set()
                )
                removed_work_areas = (
                    current_work_areas.get(mower_id, set()) - received_work_areas
                )
                if new_work_areas:
                    current_work_areas.setdefault(mower_id, set()).update(
                        new_work_areas
                    )
                    async_add_entities(
                        _create_work_area_entities(mower_id, list(new_work_areas))
                    )
                if removed_work_areas:
                    _remove_all_work_areas(removed_work_areas, mower_id)

    coordinator.async_add_listener(_async_work_area_listener)
    _async_work_area_listener()


class AutomowerNumberEntity(AutomowerControlEntity, NumberEntity):
    """Defining the AutomowerNumberEntity with AutomowerNumberEntityDescription."""

    entity_description: AutomowerNumberEntityDescription

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        description: AutomowerNumberEntityDescription,
    ) -> None:
        """Set up AutomowerNumberEntity."""
        super().__init__(mower_id, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}_{description.key}"

    @property
    def native_value(self) -> float:
        """Return the state of the number."""
        return self.entity_description.value_fn(self.mower_attributes)

    @handle_sending_exception()
    async def async_set_native_value(self, value: float) -> None:
        """Change to new number value."""
        await self.entity_description.set_value_fn(
            self.coordinator.api, self.mower_id, value
        )


class WorkAreaNumberEntity(WorkAreaControlEntity, NumberEntity):
    """Defining the WorkAreaNumberEntity with WorkAreaNumberEntityDescription."""

    entity_description: WorkAreaNumberEntityDescription

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        description: WorkAreaNumberEntityDescription,
        work_area_id: int,
    ) -> None:
        """Set up AutomowerNumberEntity."""
        super().__init__(mower_id, coordinator, work_area_id)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}_{work_area_id}_{description.key}"
        self._attr_translation_placeholders = {
            "work_area": self.work_area_attributes.name
        }

    @property
    def translation_key(self) -> str:
        """Return the translation key of the work area."""
        return self.entity_description.translation_key_fn(
            self.work_area_id, self.entity_description.key
        )

    @property
    def native_value(self) -> float:
        """Return the state of the number."""
        return self.entity_description.value_fn(self.work_area_attributes)

    @handle_sending_exception(poll_after_sending=True)
    async def async_set_native_value(self, value: float) -> None:
        """Change to new number value."""
        await self.entity_description.set_value_fn(
            self.coordinator, self.mower_id, value, self.work_area_id
        )
