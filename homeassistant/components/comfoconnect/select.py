"""Platform to control a Zehnder ComfoAir Q350/450/600 ventilation unit"""
from __future__ import annotations

import logging

from pycomfoconnect import (
    CMD_BYPASS_AUTO,
    CMD_BYPASS_OFF,
    CMD_BYPASS_ON,
    SENSOR_BYPASS_ACTIVATIONSTATE,
)

from homeassistant.components.select import (
    SelectEntity,
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED, ComfoConnectBridge

_LOGGER = logging.getLogger(__name__)
BYPASS_OPTIONS = {
    0: "Auto",
    1: "On",
    2: "Off",
}


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ComfoConnect climate platform"""
    ccb = hass.data[DOMAIN]

    add_entities([ComfoConnectBypass(ccb)], True)


class ComfoConnectBypass(SelectEntity):
    """Representation of the ComfoConnect bypass platform"""
    _attr_icon = "mdi:home-thermometer"
    _attr_should_poll = False
    sensor_bypass_activationstate_local = 0

    def __init__(self, ccb: ComfoConnectBridge) -> None:
        """Initialize the ComfoConnect bypass"""
        self._ccb = ccb
        self._attr_name = f"{ccb.name} Bypass control"
        self._attr_unique_id = f"{ccb.unique_id}-bypass-control"

    async def async_added_to_hass(self):
        """Register for sensor updates"""
        _LOGGER.debug("Registering for bypass state")

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(SENSOR_BYPASS_ACTIVATIONSTATE),
                self._handle_update_bypass,
            )
        )

        await self.hass.async_add_executor_job(
            self._ccb.comfoconnect.register_sensor, SENSOR_BYPASS_ACTIVATIONSTATE
        )

    @callback
    def _handle_update_bypass(self, value):
        """Handle update callback for bypass state"""
        _LOGGER.debug(
            "Handle update for select - bypass (%d): %s", SENSOR_BYPASS_ACTIVATIONSTATE, value
        )
        self.sensor_bypass_activationstate_local = value
        self.async_write_ha_state()


    async def async_select_option(self, option: str) -> None:
        """Change the selected option"""
        _LOGGER.debug("Set bypass option: %s", option)

        if option == BYPASS_OPTIONS[2]:
            _LOGGER.debug("Send command: CMD_BYPASS_OFF")
            self._ccb.send_cmd(CMD_BYPASS_OFF)
        elif option == BYPASS_OPTIONS[1]:
            _LOGGER.debug("Send command: CMD_BYPASS_ON")
            self._ccb.send_cmd(CMD_BYPASS_ON)
        elif option == BYPASS_OPTIONS[0]:
            _LOGGER.debug("Send command: CMD_BYPASS_AUTO")
            self._ccb.send_cmd(CMD_BYPASS_AUTO)
        else:
            raise ValueError(f"Unsupported option: {option}")

        # Update current mode
        self.schedule_update_ha_state()

    @property
    def options(self):
        """List of available options"""
        return list(BYPASS_OPTIONS.values())

    @property
    def current_option(self):
        """Return the current bypass mode. If the bypass state > 0 ComfoConenct started enabling bypass. 100% of bypass state = minimal heat recovery"""
        return BYPASS_OPTIONS[self.sensor_bypass_activationstate_local]
