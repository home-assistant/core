"""Provides fan entities for Home Connect."""

from collections import defaultdict
from collections.abc import Callable
import contextlib
from functools import partial
import logging
from typing import cast

from aiohomeconnect.model import EventKey, OptionKey
from aiohomeconnect.model.error import ActiveProgramNotSetError, HomeConnectError

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    HomeConnectApplianceData,
    HomeConnectConfigEntry,
    HomeConnectCoordinator,
)
from .entity import HomeConnectEntity
from .utils import get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

FAN_SPEED_MODE_OPTIONS = {
    "auto": "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Automatic",
    "manual": "HeatingVentilationAirConditioning.AirConditioner.EnumType.FanSpeedMode.Manual",
}
FAN_SPEED_MODE_OPTIONS_INVERTED = {v: k for k, v in FAN_SPEED_MODE_OPTIONS.items()}


AIR_CONDITIONER_ENTITY_DESCRIPTION = FanEntityDescription(
    key="air_conditioner",
    translation_key="air_conditioner",
    name=None,
)


def _create_option_entities(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
    known_entity_unique_ids: dict[str, str],
    get_option_entities_for_appliance: Callable[
        [HomeConnectConfigEntry, HomeConnectApplianceData],
        list[HomeConnectEntity],
    ],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the required option entities for the appliances."""
    option_entities_to_add = [
        entity
        for entity in get_option_entities_for_appliance(entry, appliance)
        if entity.unique_id not in known_entity_unique_ids
    ]
    known_entity_unique_ids.update(
        {
            cast(str, entity.unique_id): appliance.info.ha_id
            for entity in option_entities_to_add
        }
    )
    async_add_entities(option_entities_to_add)


def _handle_paired_or_connected_appliance(
    entry: HomeConnectConfigEntry,
    known_entity_unique_ids: dict[str, str],
    get_option_entities_for_appliance: Callable[
        [HomeConnectConfigEntry, HomeConnectApplianceData],
        list[HomeConnectEntity],
    ],
    changed_options_listener_remove_callbacks: dict[str, list[Callable[[], None]]],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Handle a new paired appliance or an appliance that has been connected.

    This function is used to handle connected events also, because some appliances
    don't report any data while they are off because they disconnect themselves
    when they are turned off, so we need to check if the entities have been added
    already or it is the first time we see them when the appliance is connected.
    """
    entities: list[HomeConnectEntity] = []
    for appliance in entry.runtime_data.data.values():
        entities_to_add = [
            entity
            for entity in get_option_entities_for_appliance(entry, appliance)
            if entity.unique_id not in known_entity_unique_ids
        ]
        for event_key in (
            EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
            EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
        ):
            changed_options_listener_remove_callback = (
                entry.runtime_data.async_add_listener(
                    partial(
                        _create_option_entities,
                        entry,
                        appliance,
                        known_entity_unique_ids,
                        get_option_entities_for_appliance,
                        async_add_entities,
                    ),
                    (appliance.info.ha_id, event_key),
                )
            )
            entry.async_on_unload(changed_options_listener_remove_callback)
            changed_options_listener_remove_callbacks[appliance.info.ha_id].append(
                changed_options_listener_remove_callback
            )
        known_entity_unique_ids.update(
            {
                cast(str, entity.unique_id): appliance.info.ha_id
                for entity in entities_to_add
            }
        )
        entities.extend(entities_to_add)
    async_add_entities(entities)


def _handle_depaired_appliance(
    entry: HomeConnectConfigEntry,
    known_entity_unique_ids: dict[str, str],
    changed_options_listener_remove_callbacks: dict[str, list[Callable[[], None]]],
) -> None:
    """Handle a removed appliance."""
    for entity_unique_id, appliance_id in known_entity_unique_ids.copy().items():
        if appliance_id not in entry.runtime_data.data:
            known_entity_unique_ids.pop(entity_unique_id, None)
            if appliance_id in changed_options_listener_remove_callbacks:
                for listener in changed_options_listener_remove_callbacks.pop(
                    appliance_id
                ):
                    listener()


def _get_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    return (
        [HomeConnectAirConditioningFanEntity(entry.runtime_data, appliance)]
        if appliance.options
        and any(
            option in appliance.options
            for option in (
                OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
                OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_PERCENTAGE,
            )
        )
        else []
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect fan entities."""
    known_entity_unique_ids: dict[str, str] = {}
    changed_options_listener_remove_callbacks: dict[str, list[Callable[[], None]]] = (
        defaultdict(list)
    )

    entry.async_on_unload(
        entry.runtime_data.async_add_special_listener(
            partial(
                _handle_paired_or_connected_appliance,
                entry,
                known_entity_unique_ids,
                _get_entities_for_appliance,
                changed_options_listener_remove_callbacks,
                async_add_entities,
            ),
            (
                EventKey.BSH_COMMON_APPLIANCE_PAIRED,
                EventKey.BSH_COMMON_APPLIANCE_CONNECTED,
            ),
        )
    )
    entry.async_on_unload(
        entry.runtime_data.async_add_special_listener(
            partial(
                _handle_depaired_appliance,
                entry,
                known_entity_unique_ids,
                changed_options_listener_remove_callbacks,
            ),
            (EventKey.BSH_COMMON_APPLIANCE_DEPAIRED,),
        )
    )


class HomeConnectAirConditioningFanEntity(HomeConnectEntity, FanEntity):
    """Representation of a Home Connect fan entity."""

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
    ) -> None:
        """Initialize the entity."""
        self._attr_preset_modes = list(FAN_SPEED_MODE_OPTIONS.keys())
        self._original_speed_modes_keys = set(FAN_SPEED_MODE_OPTIONS_INVERTED)
        super().__init__(
            coordinator,
            appliance,
            AIR_CONDITIONER_ENTITY_DESCRIPTION,
            context_override=(
                appliance.info.ha_id,
                EventKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_PERCENTAGE,
            ),
        )
        self.update_preset_mode()
        self._attr_supported_features |= FanEntityFeature.SET_SPEED

    @callback
    def _handle_coordinator_update_preset_mode(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_preset_mode()
        self.async_write_ha_state()
        _LOGGER.debug(
            "Updated %s (fan mode), new state: %s", self.entity_id, self.preset_mode
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self._handle_coordinator_update_preset_mode,
                (
                    self.appliance.info.ha_id,
                    EventKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
                ),
            )
        )

    def update_native_value(self) -> None:
        """Set the speed percentage and speed mode values."""
        option_value = None
        option_key = OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_PERCENTAGE
        if event := self.appliance.events.get(EventKey(option_key)):
            option_value = event.value
        self._attr_percentage = (
            cast(int, option_value) if option_value is not None else None
        )
        match (
            self._attr_supported_features & FanEntityFeature.SET_SPEED,
            option_key in self.appliance.options,
        ):
            case (0, True):
                self._attr_supported_features |= FanEntityFeature.SET_SPEED
            case (FanEntityFeature.SET_SPEED, False):
                self._attr_supported_features &= ~FanEntityFeature.SET_SPEED

    def update_preset_mode(self) -> None:
        """Set the preset mode value."""
        option_value = None
        option_key = OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE
        if event := self.appliance.events.get(EventKey(option_key)):
            option_value = event.value
        self._attr_preset_mode = (
            FAN_SPEED_MODE_OPTIONS_INVERTED.get(cast(str, option_value), None)
            if option_value is not None
            else None
        )
        if (
            (
                option_definition := self.appliance.options.get(
                    OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE
                )
            )
            and (option_constraints := option_definition.constraints)
            and option_constraints.allowed_values
            and self._original_speed_modes_keys
            != set(option_constraints.allowed_values)
        ):
            self._original_speed_modes_keys = {
                value
                for value in option_constraints.allowed_values
                if value is not None
            }
            self._attr_preset_modes = [
                FAN_SPEED_MODE_OPTIONS_INVERTED[option]
                for option in self._original_speed_modes_keys
                if option is not None and option in FAN_SPEED_MODE_OPTIONS_INVERTED
            ]
        match (
            self._attr_supported_features & FanEntityFeature.PRESET_MODE,
            option_key in self.appliance.options,
        ):
            case (0, True):
                self._attr_supported_features |= FanEntityFeature.PRESET_MODE
                self.__dict__.pop("supported_features", None)
            case (FanEntityFeature.PRESET_MODE, False):
                self._attr_supported_features &= ~FanEntityFeature.PRESET_MODE
                self.__dict__.pop("supported_features", None)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        try:
            # We try to set the active program option first,
            # if it fails we try to set the selected program option
            with contextlib.suppress(ActiveProgramNotSetError):
                await self.coordinator.client.set_active_program_option(
                    self.appliance.info.ha_id,
                    option_key=OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_PERCENTAGE,
                    value=percentage,
                )
                _LOGGER.debug(
                    "Updated %s's speed percentage for the active program, new state: %s",
                    self.entity_id,
                    percentage,
                )
                return

            await self.coordinator.client.set_selected_program_option(
                self.appliance.info.ha_id,
                option_key=OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_PERCENTAGE,
                value=percentage,
            )
            _LOGGER.debug(
                "Updated %s's speed percentage for the selected program, new state: %s",
                self.entity_id,
                percentage,
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_option",
                translation_placeholders=get_dict_from_home_connect_error(err),
            ) from err

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target fan mode."""
        value = FAN_SPEED_MODE_OPTIONS[preset_mode]
        try:
            # We try to set the active program option first,
            # if it fails we try to set the selected program option
            with contextlib.suppress(ActiveProgramNotSetError):
                await self.coordinator.client.set_active_program_option(
                    self.appliance.info.ha_id,
                    option_key=OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
                    value=value,
                )
                _LOGGER.debug(
                    "Updated %s's speed mode for the active program, new state: %s",
                    self.entity_id,
                    self.state,
                )
                return

            await self.coordinator.client.set_selected_program_option(
                self.appliance.info.ha_id,
                option_key=OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
                value=value,
            )
            _LOGGER.debug(
                "Updated %s's speed mode for the selected program, new state: %s",
                self.entity_id,
                self.state,
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_option",
                translation_placeholders=get_dict_from_home_connect_error(err),
            ) from err

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and any(
            option in self.appliance.options
            for option in (
                OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
                OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_PERCENTAGE,
            )
        )
