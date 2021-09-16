"""Platform to control a Zehnder ComfoAir Q350/450/600 ventilation unit."""
import logging

from pycomfoconnect import (
    CMD_BYPASS_OFF,
    CMD_BYPASS_ON,
    SENSOR_BYPASS_STATE,
    SENSOR_TEMPERATURE_SUPPLY,
)

from homeassistant.components.climate import (
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    TEMP_CELSIUS,
    ClimateEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED, ComfoConnectBridge

_LOGGER = logging.getLogger(__name__)
HVAC_MODES = [HVAC_MODE_HEAT, HVAC_MODE_COOL]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ComfoConnect climate platform."""
    if discovery_info is None:
        return

    ccb = hass.data[DOMAIN]
    add_entities([ComfoConnectBypass(ccb.name, ccb)], True)


class ComfoConnectBypass(ClimateEntity):
    """Representation of the ComfoConnect bypass platform."""

    def __init__(self, name, ccb: ComfoConnectBridge) -> None:
        """Initialize the ComfoConnect bypass."""
        self._name = name
        self._ccb = ccb
        self.sensor_temperature_supply_local = 0
        self.sensor_bypass_state_local = 0

    async def async_added_to_hass(self):
        """Register for sensor updates."""
        _LOGGER.debug("Registering for bypass state")
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(SENSOR_BYPASS_STATE),
                self._handle_update_bypass,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(SENSOR_TEMPERATURE_SUPPLY),
                self._handle_update_temp,
            )
        )
        await self.hass.async_add_executor_job(
            self._ccb.comfoconnect.register_sensor, SENSOR_BYPASS_STATE
        )
        await self.hass.async_add_executor_job(
            self._ccb.comfoconnect.register_sensor, SENSOR_TEMPERATURE_SUPPLY
        )

    @callback
    def _handle_update_bypass(self, value):
        """Handle update callback for bypass state."""
        _LOGGER.debug(
            "Handle update for climate - bypass (%d): %s", SENSOR_BYPASS_STATE, value
        )
        self.sensor_bypass_state_local = value

        self._ccb.data[SENSOR_BYPASS_STATE] = self.sensor_bypass_state_local
        self.async_write_ha_state()

    @callback
    def _handle_update_temp(self, value):
        """Handle update callback for temperature."""
        _LOGGER.debug(
            "Handle update for climate - temp (%d): %s",
            SENSOR_TEMPERATURE_SUPPLY,
            value,
        )
        self.sensor_temperature_supply_local = value

        self._ccb.data[SENSOR_TEMPERATURE_SUPPLY] = self.sensor_temperature_supply_local
        self.async_write_ha_state()

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        _LOGGER.debug("set_hvac_mode: %s", hvac_mode)

        if hvac_mode == HVAC_MODE_HEAT:
            _LOGGER.debug("Send command: CMD_BYPASS_OFF")
            self._ccb.comfoconnect.cmd_rmi_request(CMD_BYPASS_OFF)
        elif hvac_mode == HVAC_MODE_COOL:
            _LOGGER.debug("Send command: CMD_BYPASS_ON")
            self._ccb.comfoconnect.cmd_rmi_request(CMD_BYPASS_ON)
        else:
            raise ValueError(f"Unsupported hvac_mode: {hvac_mode}")

        # Update current mode
        self.schedule_update_ha_state()

    @property
    def hvac_modes(self):
        """List of available bypass modes."""
        return HVAC_MODES

    @property
    def hvac_mode(self):
        """Return the current bypass mode. If the bypass state > 0 ComfoConenct started enabling bypass. 100% of bypass state = minimal heat recovery."""
        bypass = self.sensor_bypass_state_local
        if bypass:
            return HVAC_MODE_COOL

        return HVAC_MODE_HEAT

    @property
    def supported_features(self):
        """List of available climate features. ComfoConnect does not allow to set ranges or something, so return 0."""
        return 0

    @property
    def temperature_unit(self):
        """Return celsius unit."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return current supply temperature."""
        return self.sensor_temperature_supply_local * 0.1
