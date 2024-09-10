"""Creates the number entities for the mower."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from aioautomower.model import MowerAttributes, WorkArea
from aioautomower.session import AutomowerSession

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AutomowerConfigEntry
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerControlEntity, handle_sending_exception

_LOGGER = logging.getLogger(__name__)


@callback
def _async_get_cutting_height(data: MowerAttributes) -> int:
    """Return the cutting height."""
    if TYPE_CHECKING:
        # Sensor does not get created if it is None
        assert data.settings.cutting_height is not None
    return data.settings.cutting_height


@callback
def _work_area_translation_key(work_area_id: int) -> str:
    """Return the translation key."""
    if work_area_id == 0:
        return "my_lawn_cutting_height"
    return "work_area_cutting_height"


async def async_set_work_area_cutting_height(
    coordinator: AutomowerDataUpdateCoordinator,
    mower_id: str,
    cheight: float,
    work_area_id: int,
) -> None:
    """Set cutting height for work area."""
    await coordinator.api.commands.set_cutting_height_workarea(
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
    translation_key_fn: Callable[[int], str]
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
            async_remove_entities(hass, coordinator, entry, mower_id)
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


class AutomowerWorkAreaNumberEntity(AutomowerControlEntity, NumberEntity):
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
        super().__init__(mower_id, coordinator)
        self.entity_description = description
        self.work_area_id = work_area_id
        self._attr_unique_id = f"{mower_id}_{work_area_id}_{description.key}"
        self._attr_translation_placeholders = {"work_area": self.work_area.name}

    @property
    def work_area(self) -> WorkArea:
        """Get the mower attributes of the current mower."""
        if TYPE_CHECKING:
            assert self.mower_attributes.work_areas is not None
        return self.mower_attributes.work_areas[self.work_area_id]

    @property
    def translation_key(self) -> str:
        """Return the translation key of the work area."""
        return self.entity_description.translation_key_fn(self.work_area_id)

    @property
    def native_value(self) -> float:
        """Return the state of the number."""
        return self.entity_description.value_fn(self.work_area)

    @handle_sending_exception(poll_after_sending=True)
    async def async_set_native_value(self, value: float) -> None:
        """Change to new number value."""
        await self.entity_description.set_value_fn(
            self.coordinator, self.mower_id, value, self.work_area_id
        )


@callback
def async_remove_entities(
    hass: HomeAssistant,
    coordinator: AutomowerDataUpdateCoordinator,
    entry: AutomowerConfigEntry,
    mower_id: str,
) -> None:
    """Remove deleted work areas from Home Assistant."""
    entity_reg = er.async_get(hass)
    active_work_areas = set()
    _work_areas = coordinator.data[mower_id].work_areas
    if _work_areas is not None:
        for work_area_id in _work_areas:
            uid = f"{mower_id}_{work_area_id}_cutting_height_work_area"
            active_work_areas.add(uid)
    for entity_entry in er.async_entries_for_config_entry(entity_reg, entry.entry_id):
        if (
            entity_entry.domain == Platform.NUMBER
            and (split := entity_entry.unique_id.split("_"))[0] == mower_id
            and split[-1] == "area"
            and entity_entry.unique_id not in active_work_areas
        ):
            entity_reg.async_remove(entity_entry.entity_id)
