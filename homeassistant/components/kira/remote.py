"""Support for Keene Electronics IR-IP devices."""
from __future__ import annotations

import functools as ft
import logging

from homeassistant.components import remote
from homeassistant.const import CONF_DEVICE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import CONF_REMOTE, DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Kira platform."""
    if discovery_info:
        name = discovery_info.get(CONF_NAME)
        device = discovery_info.get(CONF_DEVICE)

        kira = hass.data[DOMAIN][CONF_REMOTE][name]
        add_entities([KiraRemote(device, kira)])


class KiraRemote(Entity):
    """Remote representation used to send commands to a Kira device."""

    def __init__(self, name, kira):
        """Initialize KiraRemote class."""
        _LOGGER.debug("KiraRemote device init started for: %s", name)
        self._name = name
        self._kira = kira

    @property
    def name(self):
        """Return the Kira device's name."""
        return self._name

    def update(self):
        """No-op."""

    def send_command(self, command, **kwargs):
        """Send a command to one device."""
        for single_command in command:
            code_tuple = (single_command, kwargs.get(remote.ATTR_DEVICE))
            _LOGGER.info("Sending Command: %s to %s", *code_tuple)
            self._kira.sendCode(code_tuple)

    async def async_send_command(self, command, **kwargs):
        """Send a command to a device."""
        return await self.hass.async_add_executor_job(
            ft.partial(self.send_command, command, **kwargs)
        )
