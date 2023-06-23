"""
Switch  Platform Device for Battery Sim
"""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.dispatcher import dispatcher_send, async_dispatcher_connect

from .const import DOMAIN, CONF_BATTERY, RESET_BATTERY, GRID_IMPORT_SIM, GRID_EXPORT_SIM

_LOGGER = logging.getLogger(__name__)

BATTERY_BUTTONS =[
    {
        "name": RESET_BATTERY,
        "key":  "overide_charging_enabled",
        "icon": "mdi:fast-forward",
    }]

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add the Wiser System Switch entities."""
    handle = hass.data[DOMAIN][config_entry.entry_id]  # Get Handler

    # Add Defined Buttons
    battery_buttons = []
    for button in BATTERY_BUTTONS:
        battery_buttons.append(
            BatteryButton(handle, button["name"], button["key"], button["icon"])
        )        
    
    async_add_entities(battery_buttons)

    return True

async def async_setup_platform(hass, configuration, async_add_entities, discovery_info=None):
    if discovery_info is None:
        _LOGGER.error("This platform is only available through discovery")
        return

    for conf in discovery_info:
        battery = conf[CONF_BATTERY]
        handle = hass.data[DOMAIN][battery]
    
    battery_buttons = []
    for button in BATTERY_BUTTONS:
        battery_buttons.append(
            BatteryButton(handle, button["name"], button["key"], button["icon"])
        )
    
    async_add_entities(battery_buttons)
    return True

class BatteryButton(ButtonEntity):
    """Switch to set the status of the Wiser Operation Mode (Away/Normal)."""

    def __init__(self, handle, button_type, key, icon):
        """Initialize the sensor."""
        self._handle = handle
        self._key = key
        self._icon = icon
        self._button_type = button_type
        self._device_name = handle._name
        self._name = handle._name + " - " + button_type
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

    async def async_press(self):
        dispatcher_send(self.hass, f"{self._device_name}-BatteryResetMessage")
