"""Contec cover entity."""

import logging
from typing import List

from ContecControllers.ContecBlindActivation import BlindState, ContecBlindActivation
from ContecControllers.ControllerManager import ControllerManager

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_BLIND,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
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
    """Set up the Contec cover."""
    controllerManager: ControllerManager = hass.data[DOMAIN][config_entry.entry_id]
    allCovers: List[ContecCover] = []
    for blind in controllerManager.BlindActivations:
        allCovers.append(ContecCover(blind))
    async_add_entities(allCovers)


class ContecCover(CoverEntity):
    """Representation of an Contec cover."""

    _id: str
    _name: str
    _blindActivation: ContecBlindActivation

    def __init__(self, blindActivation: ContecBlindActivation):
        """Initialize an ContecCover."""
        self._blindActivation = blindActivation
        self._id = f"blind_{blindActivation.ControllerUnit.UnitId}-{blindActivation.StartActivationNumber}"
        self._name = f"Contec Cover {self._id}"

        def StateUpdated(movingDirection: BlindState, blindOpeningPercentage: int):
            self.schedule_update_ha_state()

        self._blindActivation.SetStateChangedCallback(StateUpdated)

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """We are evet base."""
        return False

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._id

    @property
    def is_opening(self) -> bool:
        """Return true if the cover is opening."""
        return self._blindActivation.MovingDirection == BlindState.MovingUp

    @property
    def is_closing(self) -> bool:
        """Return true if the cover is closing."""
        return self._blindActivation.MovingDirection == BlindState.MovingDown

    @property
    def is_closed(self) -> bool:
        """Return true if the cover is closed."""
        return self._blindActivation.BlindOpeningPercentage == 0

    @property
    def current_cover_position(self) -> int:
        """Return the current opening percentage."""
        return self._blindActivation.BlindOpeningPercentage

    @property
    def device_class(self) -> str:
        """Return the blind class."""
        return DEVICE_CLASS_BLIND

    @property
    def supported_features(self) -> int:
        """Return the blind supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._blindActivation.SetBlindsState(100)

    async def async_close_cover(self, **kwargs):
        """Open the cover."""
        await self._blindActivation.SetBlindsState(0)

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position: int = kwargs[ATTR_POSITION]
        await self._blindActivation.SetBlindsState(position)
