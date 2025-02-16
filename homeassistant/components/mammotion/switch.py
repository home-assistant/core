"""Support for Mammotion switches."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pymammotion.data.model.hash_list import AreaHashNameList
from pymammotion.utility.device_type import DeviceType

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from . import MammotionConfigEntry
from .coordinator import MammotionBaseUpdateCoordinator
from .entity import MammotionBaseEntity


@dataclass(frozen=True, kw_only=True)
class MammotionSwitchEntityDescription(SwitchEntityDescription):
    """Describes Mammotion switch entity."""

    key: str


@dataclass(frozen=True, kw_only=True)
class MammotionAsyncSwitchEntityDescription(MammotionSwitchEntityDescription):
    """Describes Mammotion switch entity."""

    set_fn: Callable[[MammotionBaseUpdateCoordinator, bool], Awaitable[None]]


@dataclass(frozen=True, kw_only=True)
class MammotionUpdateSwitchEntityDescription(MammotionAsyncSwitchEntityDescription):
    """Describes Mammotion switch entity."""

    is_on_func: Callable[[MammotionBaseUpdateCoordinator], bool]


@dataclass(frozen=True, kw_only=True)
class MammotionConfigSwitchEntityDescription(MammotionSwitchEntityDescription):
    """Describes Mammotion Config switch entity."""

    set_fn: Callable[[MammotionBaseUpdateCoordinator, bool], None]


@dataclass(frozen=True, kw_only=True)
class MammotionConfigAreaSwitchEntityDescription(MammotionSwitchEntityDescription):
    """Describes the Areas  entities."""

    area: str
    set_fn: Callable[[MammotionBaseUpdateCoordinator, bool, int], None]


YUKA_CONFIG_SWITCH_ENTITIES: tuple[MammotionConfigSwitchEntityDescription, ...] = (
    MammotionConfigSwitchEntityDescription(
        key="is_mow",
        set_fn=lambda coordinator, value: setattr(
            coordinator.operation_settings, "is_mow", value
        ),
    ),
    MammotionConfigSwitchEntityDescription(
        key="is_dump",
        set_fn=lambda coordinator, value: setattr(
            coordinator.operation_settings, "is_dump", value
        ),
    ),
    MammotionConfigSwitchEntityDescription(
        key="is_edge",
        set_fn=lambda coordinator, value: setattr(
            coordinator.operation_settings, "is_edge", value
        ),
    ),
)

SWITCH_ENTITIES: tuple[MammotionAsyncSwitchEntityDescription, ...] = (
    MammotionAsyncSwitchEntityDescription(
        key="blade_status",
        set_fn=lambda coordinator, value: coordinator.async_start_stop_blades(value),
    ),
    MammotionAsyncSwitchEntityDescription(
        key="side_led",
        set_fn=lambda coordinator, value: coordinator.async_set_sidelight(int(value)),
    ),
)

UPDATE_SWITCH_ENTITIES: tuple[MammotionUpdateSwitchEntityDescription, ...] = (
    MammotionUpdateSwitchEntityDescription(
        key="schedule_updates",
        is_on_func=lambda coordinator: coordinator.enabled,
        set_fn=lambda coordinator, value: coordinator.set_scheduled_updates(value),
    ),
)

CONFIG_SWITCH_ENTITIES: tuple[MammotionConfigSwitchEntityDescription, ...] = (
    MammotionConfigSwitchEntityDescription(
        key="rain_tactics",
        set_fn=lambda coordinator, value: setattr(
            coordinator.operation_settings, "rain_tactics", int(value)
        ),
    ),
)


# Example setup usage
async def async_setup_entry(
    hass: HomeAssistant, entry: MammotionConfigEntry, async_add_entities: Callable
) -> None:
    """Set up the Mammotion switch entities."""
    mammotion_devices = entry.runtime_data

    for mower in mammotion_devices:
        added_areas: set[str] = set()

        coordinator = mower.reporting_coordinator

        @callback
        def add_entities() -> None:
            """Handle addition of mowing areas."""
            if coordinator.data is None:
                return

            switch_entities: list[MammotionConfigAreaSwitchEntity] = []
            areas = list(map(str, coordinator.data.map.area.keys()))
            area_name_hashes = [
                f"{area.hash}" for area in coordinator.data.map.area_name
            ]
            area_name = coordinator.data.map.area_name
            new_areas = (set(areas) | set(area_name_hashes)) - added_areas
            if new_areas:
                for area_id in new_areas:
                    existing_name: AreaHashNameList | None = next(
                        (area for area in area_name if str(area.hash) == str(area_id)),
                        None,
                    )
                    name = (
                        existing_name.name
                        if (existing_name and existing_name.name)
                        else f"{area_id}"
                    )
                    base_area_switch_entity = (
                        MammotionConfigAreaSwitchEntityDescription(
                            key=f"{area_id}",
                            translation_key="area",
                            translation_placeholders={"name": name},
                            area=area_id,
                            name=f"{name}",
                            set_fn=lambda coord, bool_val, value: (
                                coord.operation_settings.areas.append(value)
                                if bool_val
                                else coord.operation_settings.areas.remove(value)
                            ),
                        )
                    )
                    switch_entities.append(
                        MammotionConfigAreaSwitchEntity(
                            coordinator,
                            base_area_switch_entity,
                        )
                    )
                    added_areas.add(area_id)

            if switch_entities:
                async_add_entities(switch_entities)

        add_entities()
        coordinator.async_add_listener(add_entities)

        entities = []
        for entity_description in SWITCH_ENTITIES:
            entity = MammotionSwitchEntity(coordinator, entity_description)
            entities.append(entity)

        for entity_description in CONFIG_SWITCH_ENTITIES:
            config_entity = MammotionConfigSwitchEntity(coordinator, entity_description)
            entities.append(config_entity)

        for entity_description in UPDATE_SWITCH_ENTITIES:
            config_entity = MammotionUpdateSwitchEntity(coordinator, entity_description)
            entities.append(config_entity)

        if DeviceType.is_yuka(coordinator.device_name):
            for entity_description in YUKA_CONFIG_SWITCH_ENTITIES:
                config_entity = MammotionConfigSwitchEntity(
                    coordinator, entity_description
                )
                entities.append(config_entity)
        async_add_entities(entities)


class MammotionSwitchEntity(MammotionBaseEntity, SwitchEntity):
    entity_description: MammotionSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MammotionBaseUpdateCoordinator,
        entity_description: MammotionSwitchEntityDescription,
    ) -> None:
        super().__init__(coordinator, entity_description.key)
        self.coordinator = coordinator
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.key
        self._attr_is_on = False  # Default state

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        await self.entity_description.set_fn(self.coordinator, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        await self.entity_description.set_fn(self.coordinator, False)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity state."""


class MammotionUpdateSwitchEntity(MammotionBaseEntity, SwitchEntity, RestoreEntity):
    entity_description: MammotionUpdateSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MammotionBaseUpdateCoordinator,
        entity_description: MammotionUpdateSwitchEntityDescription,
    ) -> None:
        super().__init__(coordinator, entity_description.key)
        self.coordinator = coordinator
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.key
        self._attr_is_on = True  # Default state

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_func(self.coordinator)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        await self.entity_description.set_fn(self.coordinator, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        await self.entity_description.set_fn(self.coordinator, False)
        self.async_write_ha_state()


class MammotionConfigSwitchEntity(MammotionBaseEntity, SwitchEntity, RestoreEntity):
    entity_description: MammotionConfigSwitchEntityDescription
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: MammotionBaseUpdateCoordinator,
        entity_description: MammotionConfigSwitchEntityDescription,
    ) -> None:
        super().__init__(coordinator, entity_description.key)
        self.coordinator = coordinator
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.key

    @property
    def is_on(self) -> bool:
        """Return if settings is on or off."""
        return getattr(
            self.coordinator.operation_settings, self.entity_description.key, False
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        self.entity_description.set_fn(self.coordinator, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        self.entity_description.set_fn(self.coordinator, False)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity state."""


class MammotionConfigAreaSwitchEntity(MammotionBaseEntity, SwitchEntity, RestoreEntity):
    entity_description: MammotionConfigAreaSwitchEntityDescription
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: MammotionBaseUpdateCoordinator,
        entity_description: MammotionConfigAreaSwitchEntityDescription,
    ) -> None:
        super().__init__(coordinator, entity_description.key)
        self.coordinator = coordinator
        self.entity_description = entity_description
        # TODO this should not need to be cast.
        self._attr_extra_state_attributes = {"hash": entity_description.area}
        # TODO grab defaults from operation_settings
        self._attr_is_on = False  # Default state

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        self.entity_description.set_fn(
            # TODO this should not need to be cast.
            self.coordinator,
            True,
            int(self.entity_description.area),
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        self.entity_description.set_fn(
            # TODO this should not need to be cast.
            self.coordinator,
            False,
            int(self.entity_description.area),
        )
        self.async_write_ha_state()
