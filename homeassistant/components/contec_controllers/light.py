"""Contec light entity."""

import logging
from typing import List

from ContecControllers.ContecOnOffActivation import ContecOnOffActivation
from ContecControllers.ControllerManager import ControllerManager

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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

    _name: str
    _onOffActivation: ContecOnOffActivation

    def __init__(self, onOffActivation: ContecOnOffActivation):
        """Initialize an ContecLight."""
        self._onOffActivation = onOffActivation
        self._attr_unique_id = f"light_{onOffActivation.ControllerUnit.UnitId}-{onOffActivation.StartActivationNumber}"
        self._name = f"Contec Light {self._attr_unique_id}"

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """We are evet base."""
        return False

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._onOffActivation.IsOn

    async def async_added_to_hass(self):
        """Subscribe to changes in on/off activation."""

        def StateUpdated(isOn: bool):
            self.async_write_ha_state()

        self._onOffActivation.SetStateChangedCallback(StateUpdated)

    async def async_turn_on(self, **kwargs) -> None:
        """Instruct the light to turn on."""
        await self._onOffActivation.SetActivationState(True)

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self._onOffActivation.SetActivationState(False)
