"""KIRA interface to receive UDP packets from an IR-IP bridge."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_DEVICE, CONF_NAME, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import CONF_SENSOR, DOMAIN

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:remote"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a Kira sensor."""
    if discovery_info is not None:
        name = discovery_info.get(CONF_NAME)
        device = discovery_info.get(CONF_DEVICE)
        kira = hass.data[DOMAIN][CONF_SENSOR][name]

        add_entities([KiraReceiver(device, kira)])


class KiraReceiver(SensorEntity):
    """Implementation of a Kira Receiver."""

    _attr_should_poll = False

    def __init__(self, name, kira):
        """Initialize the sensor."""
        self._name = name
        self._state = None
        self._device = STATE_UNKNOWN

        kira.registerCallback(self._update_callback)

    def _update_callback(self, code):
        code_name, device = code
        _LOGGER.debug("Kira Code: %s", code_name)
        self._state = code_name
        self._device = device
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the receiver."""
        return self._name

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def native_value(self):
        """Return the state of the receiver."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return {CONF_DEVICE: self._device}

    @property
    def force_update(self) -> bool:
        """Kira should force updates. Repeated states have meaning."""
        return True
