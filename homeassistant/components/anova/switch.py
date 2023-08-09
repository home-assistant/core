"""Support for Anova Switches."""
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from anova_wifi import AnovaException, APCUpdate

from homeassistant import config_entries
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AnovaCoordinator
from .entity import AnovaDescriptionEntity
from .models import AnovaData


@dataclass
class AnovaSwitchEntityDescriptionMixin:
    """Extra attributes for an Anova switch."""

    is_on_lambda: Callable[[APCUpdate], bool]
    turn_on_lambda: Callable[[AnovaCoordinator], Coroutine[Any, Any, None]]
    turn_off_lambda: Callable[[AnovaCoordinator], Coroutine[Any, Any, None]]


@dataclass
class AnovaSwitchDescription(
    SwitchEntityDescription, AnovaSwitchEntityDescriptionMixin
):
    """Describes an Anova switch."""


SWITCH_DESCRIPTIONS = [
    AnovaSwitchDescription(
        device_class=SwitchDeviceClass.SWITCH,
        key="precision_cooker_swtich",
        translation_key="precision_cooker_switch",
        is_on_lambda=lambda data: data.sensor.mode != "Idle",
        turn_on_lambda=lambda data: data.anova_device.set_mode("COOK"),
        turn_off_lambda=lambda data: data.anova_device.set_mode("IDLE"),
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anova device."""
    anova_data: AnovaData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AnovaSwitch(coordinator, description)
        for coordinator in anova_data.coordinators
        for description in SWITCH_DESCRIPTIONS
    )


class AnovaSwitch(AnovaDescriptionEntity, SwitchEntity):
    """Creates an Anova device that can be toggled."""

    entity_description: AnovaSwitchDescription

    @property
    def is_on(self) -> bool:
        """Determines if the Anova device is on."""
        return self.entity_description.is_on_lambda(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the Anova device on."""
        try:
            await self.entity_description.turn_on_lambda(self.coordinator)
            await self.coordinator.async_refresh()
        except AnovaException as err:
            raise HomeAssistantError("Failed to turn the switch on.") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the Anova device off."""
        try:
            await self.entity_description.turn_off_lambda(self.coordinator)
            await self.coordinator.async_refresh()
        except AnovaException as err:
            raise HomeAssistantError("Failed to turn the switch off.") from err
