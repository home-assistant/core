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
    allLights: List[ContecLight] = []
    for onOff in controllerManager.OnOffActivations:
        allLights.append(ContecLight(onOff))
    async_add_entities(allLights)


class ContecLight(LightEntity):
    """Representation of a Contec light."""

    _id: str
    _name: str
    _onOffActivation: ContecOnOffActivation

    def __init__(self, onOffActivation: ContecOnOffActivation):
        """Initialize an ContecLight."""
        self._onOffActivation = onOffActivation
        self._id = f"{onOffActivation.ControllerUnit.UnitId}-{onOffActivation.StartActivationNumber}"
        self._name = f"Contec Light {self._id}"

        def StateUpdated(isOn: bool):
            self.schedule_update_ha_state()

        self._onOffActivation.SetStateChangedCallback(StateUpdated)

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

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._id

    async def async_turn_on(self, **kwargs) -> None:
        """Instruct the light to turn on."""
        await self._onOffActivation.SetActivationState(True)

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self._onOffActivation.SetActivationState(False)
