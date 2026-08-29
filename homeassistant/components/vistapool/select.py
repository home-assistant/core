"""Vistapool Select entities."""

from dataclasses import dataclass
from typing import Any, override

from aioaquarite import AquariteError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VistapoolConfigEntry
from .const import DOMAIN, SIGNAL_NEW_POOL
from .coordinator import VistapoolDataUpdateCoordinator
from .entity import VistapoolEntity

PARALLEL_UPDATES = 1

_PUMP_MODE_OPTIONS = ["manual", "auto", "heat", "smart", "intel"]
_PUMP_SPEED_OPTIONS = ["slow", "medium", "high"]

_LIGHT_FREQUENCIES = {"daily": 86400, "weekly": 604800}
_LIGHT_MODE_PATH = "light.mode"
_LIGHT_STATUS_PATH = "light.status"

# Off and on leave schedule mode; auto only re-arms it and lets the
# controller's own schedule drive light.status. Each option must land as one
# command, or the controller sees a half-applied state.
_LIGHT_MODE_UPDATES: dict[str, dict[str, int]] = {
    "off": {_LIGHT_MODE_PATH: 0, _LIGHT_STATUS_PATH: 0},
    "on": {_LIGHT_MODE_PATH: 0, _LIGHT_STATUS_PATH: 1},
    "auto": {_LIGHT_MODE_PATH: 1},
}


@dataclass(frozen=True, kw_only=True)
class VistapoolSelectEntityDescription(SelectEntityDescription):
    """Describes a Vistapool select entity."""

    value_path: str
    # A capability flag that must be set, such as main.hasPH.
    exists_path: str | tuple[str, ...] | None = None
    # A field the controller only reports when it supports the feature. Unlike
    # exists_path this is a presence check, so a valid zero still counts.
    presence_path: str | None = None
    value_map: dict[str, int] | None = None


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
    VistapoolSelectEntityDescription(
        key="light_schedule_frequency",
        translation_key="light_schedule_frequency",
        entity_category=EntityCategory.CONFIG,
        options=list(_LIGHT_FREQUENCIES),
        value_path="light.freq",
        presence_path="light.freq",
        value_map=_LIGHT_FREQUENCIES,
    ),
)


def _build_select_entities(
    coordinator: VistapoolDataUpdateCoordinator,
) -> list[SelectEntity]:
    """Build the select entities for a single pool."""
    entities: list[SelectEntity] = []
    for description in SELECT_DESCRIPTIONS:
        if description.exists_path is not None:
            required = (
                (description.exists_path,)
                if isinstance(description.exists_path, str)
                else description.exists_path
            )
            if not all(coordinator.get_value(path) for path in required):
                continue
        if (
            description.presence_path is not None
            and coordinator.get_value(description.presence_path) is None
        ):
            continue
        entities.append(VistapoolSelect(coordinator, description))
    if coordinator.get_value(_LIGHT_MODE_PATH) is not None:
        entities.append(VistapoolLightModeSelect(coordinator))
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VistapoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vistapool select entities for every pool on the account."""
    entities: list[SelectEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        entities.extend(_build_select_entities(coordinator))
    async_add_entities(entities)

    @callback
    def _async_add_pool(coordinator: VistapoolDataUpdateCoordinator) -> None:
        async_add_entities(_build_select_entities(coordinator))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_NEW_POOL}_{entry.entry_id}", _async_add_pool
        )
    )


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

    @property
    @override
    def current_option(self) -> str | None:
        """Return the option that maps to the current API value."""
        raw = _to_index(self.coordinator.get_value(self.entity_description.value_path))
        if raw is None:
            return None
        if (value_map := self.entity_description.value_map) is not None:
            return next(
                (option for option, value in value_map.items() if value == raw), None
            )
        options = self.entity_description.options or []
        if not 0 <= raw < len(options):
            return None
        return options[raw]

    @override
    async def async_select_option(self, option: str) -> None:
        """Send the chosen option to the controller."""
        if (value_map := self.entity_description.value_map) is not None:
            value = value_map[option]
        else:
            assert self.entity_description.options is not None
            value = self.entity_description.options.index(option)
        try:
            await self.coordinator.api.set_value(
                self.coordinator.pool_id,
                self.entity_description.value_path,
                value,
            )
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={"entity": self.entity_id},
            ) from err
        self.coordinator.apply_optimistic(self.entity_description.value_path, value)


class VistapoolLightModeSelect(VistapoolEntity, SelectEntity):
    """Pool light mode: off, on, or the controller's own schedule.

    Off and on need light.mode and light.status written together, so this
    writes through set_values rather than the single-value helper.
    """

    _attr_translation_key = "light_mode"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(_LIGHT_MODE_UPDATES)

    def __init__(self, coordinator: VistapoolDataUpdateCoordinator) -> None:
        """Initialize the light mode select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = self.build_unique_id("light_mode")

    @property
    @override
    def current_option(self) -> str | None:
        """Return auto while the schedule is armed, else the on/off state."""
        mode = _to_index(self.coordinator.get_value(_LIGHT_MODE_PATH))
        if mode is None:
            return None
        if mode == 1:
            return "auto"
        status = _to_index(self.coordinator.get_value(_LIGHT_STATUS_PATH))
        if status is None:
            return None
        return "on" if status == 1 else "off"

    @override
    async def async_select_option(self, option: str) -> None:
        """Send the option's field set to the controller as one command."""
        updates = _LIGHT_MODE_UPDATES[option]
        try:
            await self.coordinator.api.set_values(self.coordinator.pool_id, updates)
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={"entity": self.entity_id},
            ) from err
        self.coordinator.apply_optimistic_values(updates)
