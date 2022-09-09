"""Support for HDMI CEC devices as switches."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import ATTR_NEW, DOMAIN, CecEntity

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = SWITCH_DOMAIN + ".{}"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Find and return HDMI devices as switches."""
    if discovery_info and ATTR_NEW in discovery_info:
        _LOGGER.info("Setting up HDMI devices %s", discovery_info[ATTR_NEW])
        entities = []
        for device in discovery_info[ATTR_NEW]:
            hdmi_device = hass.data[DOMAIN][device]
            entities.append(CecSwitchEntity(hdmi_device, hdmi_device.logical_address))
        add_entities(entities, True)


class CecSwitchEntity(CecEntity, SwitchEntity):
    """Representation of a HDMI device as a Switch."""

    def __init__(self, device, logical) -> None:
        """Initialize the HDMI device."""
        CecEntity.__init__(self, device, logical)
        self.entity_id = f"{SWITCH_DOMAIN}.hdmi_{hex(self._logical_address)[2:]}"

    def turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        self._device.turn_on()
        self._state = STATE_ON
        self.schedule_update_ha_state(force_refresh=False)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        self._device.turn_off()
        self._state = STATE_OFF
        self.schedule_update_ha_state(force_refresh=False)

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._state == STATE_ON
