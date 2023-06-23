"""
Switch  Platform Device for Battery Sim
"""
import logging

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN, CONF_BATTERY, OVERIDE_CHARGING, PAUSE_BATTERY, FORCE_DISCHARGE, CHARGE_ONLY

_LOGGER = logging.getLogger(__name__)

BATTERY_SWITCHES = [
    {
        "name": OVERIDE_CHARGING,
        "key":  "overide_charging_enabled",
        "icon": "mdi:fast-forward",
    },
    {
        "name": PAUSE_BATTERY,
        "key":  "pause_battery_enabled",
        "icon": "mdi:pause",
    },
    {
        "name": FORCE_DISCHARGE,
        "key": "force_battery_enabled",
        "icon": "mdi:home-export-outline"
    },
    {
        "name": CHARGE_ONLY,
        "key": "charge_only_enabled",
        "icon": "mdi:home-import-outline"
    }
]

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add the Wiser System Switch entities."""
    handle = hass.data[DOMAIN][config_entry.entry_id]  # Get Handler

    # Add Defined Switches
    battery_switches = []
    for switch in BATTERY_SWITCHES:
        battery_switches.append(
            BatterySwitch(handle, switch["name"], switch["key"], switch["icon"])
        )        
    
    async_add_entities(battery_switches)

    return True

async def async_setup_platform(hass, configuration, async_add_entities, discovery_info=None):
    if discovery_info is None:
        _LOGGER.error("This platform is only available through discovery")
        return

    for conf in discovery_info:
        battery = conf[CONF_BATTERY]
        handle = hass.data[DOMAIN][battery]
    
    battery_switches = []
    for switch in BATTERY_SWITCHES:
        battery_switches.append(
            BatterySwitch(handle, switch["name"], switch["key"], switch["icon"])
        )
    
    async_add_entities(battery_switches)
    return True

class BatterySwitch(SwitchEntity):
    """Switch to set the status of the Wiser Operation Mode (Away/Normal)."""

    def __init__(self, handle, switch_type, key, icon):
        """Initialize the sensor."""
        self.handle = handle
        self._key = key
        self._icon = icon
        self._switch_type = switch_type
        self._device_name = handle._name
        self._name = handle._name + " - " + switch_type
        self._is_on = False
        self._type = type

    @property
    def unique_id(self):
        """Return uniqueid."""
        return self._name

    @property
    def name(self):
        return self._name

    @property
    def device_info(self):
        return {
                "name": self._device_name,
                "identifiers": {
                    (DOMAIN, self._device_name)
                },
            }

    @property
    def icon(self):
        """Return icon."""
        return self._icon

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.handle._switches[self._switch_type]

    async def async_turn_on(self, **kwargs):
        self.handle._switches[self._switch_type] = True
        if self._switch_type == CHARGE_ONLY:
            self.handle._switches[FORCE_DISCHARGE] = False
        elif self._switch_type == FORCE_DISCHARGE:
            self.handle._switches[CHARGE_ONLY] = False
        self.schedule_update_ha_state(True)
        return True

    async def async_turn_off(self, **kwargs):
        self.handle._switches[self._switch_type] = False
        self.schedule_update_ha_state(True)
        return True
