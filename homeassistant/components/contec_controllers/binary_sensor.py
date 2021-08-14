"""Contec Pusher."""

import logging
from typing import List

from ContecControllers.ContecPusherActivation import ContecPusherActivation
from ContecControllers.ControllerManager import ControllerManager

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up the Contec Pushers."""
    controllerManager: ControllerManager = hass.data[DOMAIN][config_entry.entry_id]
    allPusherss: List[ContecPusher] = []
    for pusher in controllerManager.PusherActivations:
        allPusherss.append(ContecPusher(pusher))
    async_add_entities(allPusherss)


class ContecPusher(BinarySensorEntity):
    """Representation of a Contec Pusher."""

    _id: str
    _name: str
    _pusherActivation: ContecPusherActivation

    def __init__(self, pusherActivation: ContecPusherActivation):
        """Initialize an ContecPusher."""
        self._pusherActivation = pusherActivation
        self._id = f"pusher_{pusherActivation.ControllerUnit.UnitId}-{pusherActivation.StartActivationNumber}"
        self._name = f"Contec Pusher {self._id}"

        def StateUpdated(isPushed: bool):
            self.schedule_update_ha_state()

        self._pusherActivation.SetStateChangedCallback(StateUpdated)

    @property
    def name(self) -> str:
        """Return the display name of this pusher."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """We are evet base."""
        return False

    @property
    def is_on(self) -> bool:
        """Return true if pusher is on."""
        return self._pusherActivation.IsPushed

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._id
