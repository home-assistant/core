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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AutomowerConfigEntry
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import (
    AutomowerControlEntity,
    WorkAreaControlEntity,
    _work_area_translation_key,
    async_remove_work_area_entities,
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


NUMBER_TYPES: tuple[AutomowerNumberEntityDescription, ...] = (
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
class AutomowerWorkAreaNumberEntityDescription(NumberEntityDescription):
    """Describes Automower work area number entity."""

    value_fn: Callable[[WorkArea], int]
    translation_key_fn: Callable[[int, str], str]
    set_value_fn: Callable[
        [AutomowerDataUpdateCoordinator, str, float, int], Awaitable[Any]
    ]


WORK_AREA_NUMBER_TYPES: tuple[AutomowerWorkAreaNumberEntityDescription, ...] = (
    AutomowerWorkAreaNumberEntityDescription(
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

    for mower_id in coordinator.data:
        if coordinator.data[mower_id].capabilities.work_areas:
            _work_areas = coordinator.data[mower_id].work_areas
            if _work_areas is not None:
                entities.extend(
                    AutomowerWorkAreaNumberEntity(
                        mower_id, coordinator, description, work_area_id
                    )
                    for description in WORK_AREA_NUMBER_TYPES
                    for work_area_id in _work_areas
                )
            async_remove_work_area_entities(hass, coordinator, entry, mower_id)
        entities.extend(
            AutomowerNumberEntity(mower_id, coordinator, description)
            for description in NUMBER_TYPES
            if description.exists_fn(coordinator.data[mower_id])
        )
    async_add_entities(entities)


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


class AutomowerWorkAreaNumberEntity(WorkAreaControlEntity, NumberEntity):
    """Defining the AutomowerWorkAreaNumberEntity with AutomowerWorkAreaNumberEntityDescription."""

    entity_description: AutomowerWorkAreaNumberEntityDescription

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        description: AutomowerWorkAreaNumberEntityDescription,
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
