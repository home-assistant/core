"""Contec light entity."""

import logging
from typing import List

from ContecControllers.ContecOnOffActivation import ContecOnOffActivation
from ContecControllers.ControllerManager import ControllerManager

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Contec Lights."""
    controllerManager: ControllerManager = hass.data[DOMAIN][config_entry.entry_id]
    allLights: List[ContecLight] = [
        ContecLight(onOff) for onOff in controllerManager.OnOffActivations
    ]
    async_add_entities(allLights)


class ContecLight(LightEntity):
    """Representation of a Contec light."""

    _on_off_activation: ContecOnOffActivation

    def __init__(self, on_off_activation: ContecOnOffActivation):
        """Initialize an ContecLight."""
        self._on_off_activation = on_off_activation
        self._attr_unique_id = f"{on_off_activation.ControllerUnit.UnitId}-{on_off_activation.StartActivationNumber}"
        self._attr_name = f"Contec Light {self._attr_unique_id}"
        self._attr_should_poll = False

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._on_off_activation.IsOn

    async def async_added_to_hass(self):
        """Subscribe to changes in on/off activation."""

        @callback
        def StateUpdated(isOn: bool):
            self.async_write_ha_state()

        self._on_off_activation.SetStateChangedCallback(StateUpdated)

    async def async_turn_on(self, **kwargs) -> None:
        """Instruct the light to turn on."""
        await self._on_off_activation.SetActivationState(True)

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self._on_off_activation.SetActivationState(False)
