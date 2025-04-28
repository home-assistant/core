"""Platform for Miele fan entity."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from typing import Any, Final

from aiohttp import ClientResponseError

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from .const import DOMAIN, POWER_OFF, POWER_ON, VENTILATION_STEP, MieleAppliance
from .coordinator import MieleConfigEntry, MieleDataUpdateCoordinator
from .entity import MieleEntity

_LOGGER = logging.getLogger(__name__)

SPEED_RANGE = (1, 4)

# FAN_READ_ONLY = [MieleAppliance.HOB_INDUCT_EXTR]


@dataclass(frozen=True, kw_only=True)
class MieleFanDefinition:
    """Class for defining fan entities."""

    types: tuple[MieleAppliance, ...]
    description: FanEntityDescription


FAN_TYPES: Final[tuple[MieleFanDefinition, ...]] = (
    MieleFanDefinition(
        types=(MieleAppliance.HOOD,),
        description=FanEntityDescription(
            key="fan",
            translation_key="fan",
        ),
    ),
    MieleFanDefinition(
        types=(MieleAppliance.HOB_INDUCT_EXTR,),
        description=FanEntityDescription(
            key="fan_readonly",
            translation_key="fan",
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MieleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the fan platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        MieleFan(coordinator, device_id, definition.description)
        for device_id, device in coordinator.data.devices.items()
        for definition in FAN_TYPES
        if device.device_type in definition.types
    )


class MieleFan(MieleEntity, FanEntity):
    """Representation of a Fan."""

    entity_description: FanEntityDescription

    def __init__(
        self,
        coordinator: MieleDataUpdateCoordinator,
        device_id: str,
        description: FanEntityDescription,
    ) -> None:
        """Initialize the fan."""

        self._attr_supported_features: FanEntityFeature = (
            FanEntityFeature(0)
            if description.key == "fan_readonly"
            else FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )
        super().__init__(coordinator, device_id, description)

    @property
    def is_on(self) -> bool:
        """Return current on/off state."""
        assert self.device.state_ventilation_step is not None
        return self.device.state_ventilation_step > 0

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return ranged_value_to_percentage(
            SPEED_RANGE,
            (self.device.state_ventilation_step or 0),
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Set_percentage: %s", percentage)
        ventilation_step = math.ceil(
            percentage_to_ranged_value(SPEED_RANGE, percentage)
        )
        _LOGGER.debug("Calc ventilation_step: %s", ventilation_step)
        if ventilation_step == 0:
            await self.async_turn_off()
        else:
            try:
                await self.api.send_action(
                    self._device_id, {VENTILATION_STEP: ventilation_step}
                )
            except ClientResponseError as ex:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="set_state_error",
                    translation_placeholders={
                        "entity": self.entity_id,
                    },
                ) from ex
            self.device.state_ventilation_step = ventilation_step
            self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        _LOGGER.debug(
            "Turn_on -> percentage: %s, preset_mode: %s", percentage, preset_mode
        )
        try:
            await self.api.send_action(self._device_id, {POWER_ON: True})
        except ClientResponseError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_state_error",
                translation_placeholders={
                    "entity": self.entity_id,
                },
            ) from ex

        if percentage is not None:
            await self.async_set_percentage(percentage)
            return

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        try:
            await self.api.send_action(self._device_id, {POWER_OFF: True})
        except ClientResponseError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_state_error",
                translation_placeholders={
                    "entity": self.entity_id,
                },
            ) from ex

        self.device.state_ventilation_step = 0
        self.async_write_ha_state()
