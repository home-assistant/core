"""Support for Synology Surveillance Station Cameras."""
import logging
from typing import Any

import requests
from synology.surveillance_station import SurveillanceStation

from homeassistant.components.switch import SwitchDevice

from .const import DATA_NAME, DATA_SYNOLOGY_CLIENT, DOMAIN_DATA

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a Synology Switches."""
    if hass.data[DOMAIN_DATA]:
        synology_client = hass.data[DOMAIN_DATA][DATA_SYNOLOGY_CLIENT]
        if synology_client:
            switches = [
                SurveillanceHomeModeSwitch(
                    synology_client, hass.data[DOMAIN_DATA][DATA_NAME]
                )
            ]
            async_add_entities(switches)


class SurveillanceHomeModeSwitch(SwitchDevice):
    """Synology Surveillance Station Home Mode toggle."""

    def __init__(self, synology_client: SurveillanceStation, name):
        """Initialize a Home Mode toggle."""
        super().__init__()
        self._synology_client = synology_client
        self._name = f"{name} Surveillance HomeMode Switch"

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return True if Home Mode is enabled."""
        try:
            return self._synology_client.get_home_mode_status()
        except (requests.exceptions.RequestException):
            _LOGGER.exception("Error when trying to get the status", exc_info=True)
            return False

    def turn_on(self, **kwargs: Any) -> None:
        """Enable Home Mode."""
        try:
            self._synology_client.set_home_mode(True)
        except (requests.exceptions.RequestException):
            _LOGGER.exception("Error when trying to enable home mode", exc_info=True)

    def turn_off(self, **kwargs: Any) -> None:
        """Disable Home Mode."""
        try:
            self._synology_client.set_home_mode(False)
        except (requests.exceptions.RequestException):
            _LOGGER.exception("Error when trying to disable home mode", exc_info=True)
