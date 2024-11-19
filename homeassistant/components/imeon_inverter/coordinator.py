"""Coordinator for Imeon integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from imeon_inverter_api.inverter import Inverter

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import HUBNAME

_LOGGER = logging.getLogger(__name__)


# HUB CREATION #
class InverterCoordinator(DataUpdateCoordinator):
    """Abstract representation of an inverter.

    A HUB or a data update coordinator is a HASS Object that automatically polls
    data at regular intervals. Entities representing the different sensors and
    settings then all poll data from their HUB. Each inverter is it's own HUB
    thus it's own data set. This allows this integration to handle as many
    inverters as possible in parallel.
    """

    _HUBs: dict[Any, InverterCoordinator] = {}

    # Implement methods to fetch and update data
    def __init__(
        self,
        hass: HomeAssistant,
        user_input: dict[str, Any] | None = None,
        uuid=0,
        title=HUBNAME,
    ) -> None:
        """Initialize data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=HUBNAME,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(minutes=1),
            always_update=True,
        )

        if user_input is None:
            raise ValueError("user_input cannot be None")

        self.api = Inverter(user_input["address"])  # API calls
        self.username = user_input["username"]
        self.password = user_input["password"]
        self.friendly_name = title

        # unique ID
        self.__id = uuid
        InverterCoordinator._HUBs[str(self.__id)] = self

        # Store request data
        self.data = {}
        self.first_call = True

    def update(self, user_input: dict[str, Any]) -> None:
        """Update HUB data based on user input."""
        self.api = Inverter(user_input["address"])
        self.username = user_input["username"]
        self.password = user_input["password"]
        self.first_call = True

    @property
    def id(self):
        """Getter for id."""
        return self.__id

    @staticmethod
    def get_from_id(id) -> InverterCoordinator:
        """Getter for InverterCoordinator."""
        try:
            return InverterCoordinator._HUBs[str(id)]
        except IndexError:
            raise IndexError(f"Incorrect HUB ID ({id!s}) .") from None
