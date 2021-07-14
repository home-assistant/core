import logging

from homeassistant.components.switch import SwitchEntity

from . import DroneMobileEntity
from .const import DOMAIN, SWITCHES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add the Switch Entities from the config."""
    entry = hass.data[DOMAIN][config_entry.entry_id]
    switches = []
    for key, value in SWITCHES.items():
        async_add_entities([Switch(entry, key)], True)
        
class Switch(DroneMobileEntity,SwitchEntity):
    def __init__(self, coordinator, switch):
        """Initialize."""
        super().__init__(
            device_id="dronemobile_" + switch,
            name=coordinator.data["vehicle_name"] + "_" + switch,
            coordinator=coordinator,
        )
        self._switch = switch
        self._state = self.is_on
    
    async def async_turn_on(self, **kwargs):
        """switches on the vehicle device."""
        if self.is_on:
            return
        _LOGGER.debug("switching on %s " + self._switch, self.coordinator.data['vehicle_name'])
        command_call = None
        if self._switch == "remoteStart":
            command_call = self.coordinator.vehicle.start
        elif self._switch == "panic":
            command_call = self.coordinator.vehicle.panic_on
        elif self._switch == "aux1":
            command_call = self.coordinator.vehicle.aux1
        elif self._switch == "aux2":
            command_call = self.coordinator.vehicle.aux2
        else:
            return
        response = await self.coordinator.hass.async_add_executor_job(
            command_call, self.coordinator.data["device_key"]
        )
        await self.coordinator.hass.async_add_executor_job(
            self.coordinator.update_data_from_response, self.coordinator, response
        )
        self._state = self.get_is_on_value(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """switches off the vehicle device."""
        if not self.is_on:
            return
        _LOGGER.debug("Switching off %s " + self._switch, self.coordinator.data['vehicle_name'])
        command_call = None
        if self._switch == "remoteStart":
            command_call = self.coordinator.vehicle.stop
        elif self._switch == "panic":
            command_call = self.coordinator.vehicle.panic_off
        else:
            return
        response = await self.coordinator.hass.async_add_executor_job(
            command_call, self.coordinator.data["device_key"]
        )
        await self.coordinator.hass.async_add_executor_job(
            self.coordinator.update_data_from_response, self.coordinator, response
        )
        self._state = self.get_is_on_value(True)
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs):
        """Toggles the vehicle switch."""
        _LOGGER.debug("Toggling %s " + self._switch, self.coordinator.data['vehicle_name'])
        command_call = None
        if self._switch == "remoteStart":
            if self.is_on:
                command_call = self.coordinator.vehicle.remoteStop
            else:
                command_call = self.coordinator.vehicle.remoteStart
        elif self._switch == "panic":
            if self.is_on:
                command_call = self.coordinator.vehicle.panic_off
            else:
                command_call = self.coordinator.vehicle.panic_on
        elif self._switch == "aux1":
            command_call = self.coordinator.vehicle.aux1
        elif self._switch == "aux2":
            command_call = self.coordinator.vehicle.aux2
            return
        response = await self.coordinator.hass.async_add_executor_job(
            command_call, self.coordinator.data["device_key"]
        )
        await self.coordinator.hass.async_add_executor_job(
            self.coordinator.update_data_from_response, self.coordinator, response
        )
        self._state = self.get_is_on_value(True)
        self.async_write_ha_state()

    # Need to remove @property decorator in order to be able to change logic based on where the call to is_on is made from.
    def get_is_on_value(self, calledFromAction=False):
        """Determine if the switch is switched."""
        if self._switch == "remoteStart":
            if (self.coordinator.data is None or self.coordinator.data["last_known_state"]["controller"]["engine_on"] is None):
                return None
            if calledFromAction:
                return self.coordinator.data["remote_start_status"] == True
            else:
                return (self.coordinator.data["last_known_state"]["controller"]["engine_on"] == True or self.coordinator.data["last_known_state"]["controller"]["ignition_on"] == True)
        elif self._switch == "panic":
            if (self.coordinator.data is None or self.coordinator.data["panic_status"] is None):
                return None
            return self.coordinator.data["panic_status"] == True
        # Aux1 and Aux2 are momentary switches that can only be turned on. So, we will set their value to off.
        elif self._switch == "aux1":
            return False
        elif self._switch == "aux2":
            return False
        else:
            _LOGGER.error("Entry not found in SWITCHES: " + self._switch)
    
    is_on = property(get_is_on_value)

    @property
    def icon(self):
        return SWITCHES[self._switch]["icon"]
