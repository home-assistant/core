"""Provides fan entities for Home Connect."""

import contextlib
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

from .common import setup_home_connect_entry
from .const import DOMAIN
from .coordinator import HomeConnectApplianceCoordinator, HomeConnectConfigEntry
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


def _get_entities_for_appliance(
    appliance_coordinator: HomeConnectApplianceCoordinator,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    return (
        [HomeConnectAirConditioningFanEntity(appliance_coordinator)]
        if appliance_coordinator.data.options
        and any(
            option in appliance_coordinator.data.options
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
    setup_home_connect_entry(
        hass,
        entry,
        _get_entities_for_appliance,
        async_add_entities,
        lambda appliance_coordinator, _: _get_entities_for_appliance(
            appliance_coordinator
        ),
    )


class HomeConnectAirConditioningFanEntity(HomeConnectEntity, FanEntity):
    """Representation of a Home Connect fan entity."""

    def __init__(
        self,
        coordinator: HomeConnectApplianceCoordinator,
    ) -> None:
        """Initialize the entity."""
        self._attr_preset_modes = list(FAN_SPEED_MODE_OPTIONS.keys())
        self._original_speed_modes_keys = set(FAN_SPEED_MODE_OPTIONS_INVERTED)
        super().__init__(
            coordinator,
            AIR_CONDITIONER_ENTITY_DESCRIPTION,
            context_override=(
                EventKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_PERCENTAGE
            ),
        )
        self.update_preset_mode()

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
                EventKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
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

    @property
    def supported_features(self) -> FanEntityFeature:
        """Return the supported features for this fan entity."""
        features = FanEntityFeature(0)
        if (
            OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_PERCENTAGE
            in self.appliance.options
        ):
            features |= FanEntityFeature.SET_SPEED
        if (
            OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE
            in self.appliance.options
        ):
            features |= FanEntityFeature.PRESET_MODE
        return features

    def update_preset_mode(self) -> None:
        """Set the preset mode value."""
        option_value = None
        option_key = OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE
        if event := self.appliance.events.get(EventKey(option_key)):
            option_value = event.value
        self._attr_preset_mode = (
            FAN_SPEED_MODE_OPTIONS_INVERTED.get(cast(str, option_value))
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
            and (
                allowed_values_without_none := {
                    value
                    for value in option_constraints.allowed_values
                    if value is not None
                }
            )
            and self._original_speed_modes_keys != allowed_values_without_none
        ):
            self._original_speed_modes_keys = allowed_values_without_none
            self._attr_preset_modes = [
                key
                for key, value in FAN_SPEED_MODE_OPTIONS.items()
                if value in self._original_speed_modes_keys
            ]

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        await self._async_set_option(
            OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_PERCENTAGE,
            percentage,
        )
        _LOGGER.debug(
            "Updated %s's speed percentage option, new state: %s",
            self.entity_id,
            percentage,
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target fan mode."""
        await self._async_set_option(
            OptionKey.HEATING_VENTILATION_AIR_CONDITIONING_AIR_CONDITIONER_FAN_SPEED_MODE,
            FAN_SPEED_MODE_OPTIONS[preset_mode],
        )
        _LOGGER.debug(
            "Updated %s's speed mode option, new state: %s",
            self.entity_id,
            self.state,
        )

    async def _async_set_option(self, key: OptionKey, value: str | int) -> None:
        """Set an option for the entity."""
        try:
            # We try to set the active program option first,
            # if it fails we try to set the selected program option
            with contextlib.suppress(ActiveProgramNotSetError):
                await self.coordinator.client.set_active_program_option(
                    self.appliance.info.ha_id,
                    option_key=key,
                    value=value,
                )
                return

            await self.coordinator.client.set_selected_program_option(
                self.appliance.info.ha_id,
                option_key=key,
                value=value,
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
