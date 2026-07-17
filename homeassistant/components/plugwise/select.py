"""Plugwise Select component for Home Assistant."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from plugwise import Smile

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DHW_MODE,
    LOCATION,
    SELECT_DHW_MODE,
    SELECT_GATEWAY_MODE,
    SELECT_REGULATION_MODE,
    SELECT_SCHEDULE,
    SELECT_ZONE_PROFILE,
    SelectOptionsType,
    SelectType,
)
from .coordinator import PlugwiseConfigEntry, PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import plugwise_command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PlugwiseSelectEntityDescription(SelectEntityDescription):
    """Class describing Plugwise Select entities."""

    key: SelectType
    options_key: SelectOptionsType
    set_value_fn: Callable[[Smile, str, str, str, int | str], Awaitable[None]]


SELECT_TYPES = (
    PlugwiseSelectEntityDescription(
        key=DHW_MODE,
        translation_key=SELECT_DHW_MODE,
        entity_category=EntityCategory.CONFIG,
        options_key="dhw_modes",
        set_value_fn=lambda api, key, appl_id, option, length: api.set_dhw_mode(
            key, appl_id, option, length
        ),
    ),
    PlugwiseSelectEntityDescription(
        key=SELECT_SCHEDULE,
        translation_key=SELECT_SCHEDULE,
        options_key="available_schedules",
        set_value_fn=lambda api, key, appl_or_loc_id, option, state: api.set_select(
            key, appl_or_loc_id, option, state
        ),
    ),
    PlugwiseSelectEntityDescription(
        key=SELECT_REGULATION_MODE,
        translation_key=SELECT_REGULATION_MODE,
        entity_category=EntityCategory.CONFIG,
        options_key="regulation_modes",
        set_value_fn=lambda api, key, appl_or_loc_id, option, state: api.set_select(
            key, appl_or_loc_id, option, state
        ),
    ),
    PlugwiseSelectEntityDescription(
        key=SELECT_DHW_MODE,
        translation_key=SELECT_DHW_MODE,
        entity_category=EntityCategory.CONFIG,
        options_key="dhw_modes",
        set_value_fn=lambda api, key, appl_or_loc_id, option, state: api.set_select(
            key, appl_or_loc_id, option, state
        ),
    ),
    PlugwiseSelectEntityDescription(
        key=SELECT_GATEWAY_MODE,
        translation_key=SELECT_GATEWAY_MODE,
        entity_category=EntityCategory.CONFIG,
        options_key="gateway_modes",
        set_value_fn=lambda api, key, appl_or_loc_id, option, state: (
            api.set_dset_selecthw_mode(key, appl_or_loc_id, option, state)
        ),
    ),
    PlugwiseSelectEntityDescription(
        key=SELECT_ZONE_PROFILE,
        translation_key=SELECT_ZONE_PROFILE,
        entity_category=EntityCategory.CONFIG,
        options_key="zone_profiles",
        set_value_fn=lambda api, key, appl_or_loc_id, option, state: api.set_select(
            key, appl_or_loc_id, option, state
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlugwiseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Smile selector from a config entry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities() -> None:
        """Add Entities."""
        if not coordinator.new_devices:
            return

        async_add_entities(
            PlugwiseSelectEntity(coordinator, device_id, description)
            for device_id in coordinator.new_devices
            for description in SELECT_TYPES
            if coordinator.data[device_id].get(description.key)
        )

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class PlugwiseSelectEntity(PlugwiseEntity, SelectEntity):
    """Represent Smile selector."""

    entity_description: PlugwiseSelectEntityDescription

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
        entity_description: PlugwiseSelectEntityDescription,
    ) -> None:
        """Initialise the selector."""
        super().__init__(coordinator, device_id)
        suffix = entity_description.key
        if entity_description.key == DHW_MODE:
            suffix = SELECT_DHW_MODE
        self._attr_unique_id = f"{device_id}-{suffix}"
        self.entity_description = entity_description

        self._device_or_location = device_id
        if (
            self.entity_description.key in (SELECT_SCHEDULE, SELECT_ZONE_PROFILE)
            and (location := self.device.get(LOCATION)) is not None
        ):
            self._device_or_location = location

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.device[self.entity_description.key]

    @property
    @override
    def options(self) -> list[str]:
        """Return the available select-options."""
        return self.device[self.entity_description.options_key]

    @plugwise_command
    @override
    async def async_select_option(self, option: str) -> None:
        """Change to the selected entity option.

        The appliance ID (= device_id) is required for the dhw_mode select.
        The location ID is required for the thermostat schedule and zone_profile selects.
        STATE_ON is required for the thermostat schedule select.
        """
        select_options_count: int | str = len(self.options)
        if self.entity_description.key != DHW_MODE:
            select_options_count = STATE_ON
        await self.entity_description.set_value_fn(
            self.coordinator.api,
            self.entity_description.key,
            self._device_or_location,
            option,
            select_options_count,
        )
