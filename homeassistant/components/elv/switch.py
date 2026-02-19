"""Support for PCA 301 smart switch."""

from __future__ import annotations

import logging
from typing import Any

import pypca
from serial import SerialException

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the PCA switch platform."""

    if discovery_info is None:
        return

    serial_device = discovery_info["device"]

    try:
        pca = pypca.PCA(serial_device)
        pca.open()

        entities = [SmartPlugSwitch(pca, device) for device in pca.get_devices()]
        add_entities(entities, True)

    except SerialException as exc:
        _LOGGER.warning("Unable to open serial port: %s", exc)
        return

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, pca.close)

    pca.start_scan()


class SmartPlugSwitch(SwitchEntity):
    """Representation of a PCA Smart Plug switch."""

    def __init__(self, pca, device_id):
        """Initialize the switch."""
        self._device_id = device_id
        self._attr_name = "PCA 301"
        self._pca = pca

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._pca.turn_on(self._device_id)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._pca.turn_off(self._device_id)

    def update(self) -> None:
        """Update the PCA switch's state."""
        try:
            self._attr_is_on = self._pca.get_state(self._device_id)
            self._attr_available = True

        except OSError as ex:
            if self._attr_available:
                _LOGGER.warning("Could not read state for %s: %s", self.name, ex)
                self._attr_available = False
