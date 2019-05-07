"""Device tracker platform that adds support for Leaf Spy."""
import logging

from homeassistant.components.device_tracker import (
    ATTR_SOURCE_TYPE, SOURCE_TYPE_GPS)
from homeassistant.util import slugify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLUG_STATES = [
    "Not Plugged In",
    "Partially Plugged In"
    "Plugged In"
]

CHARGE_MODES = [
    "Not Charging",
    "Level 1 Charging (100-120 Volts)",
    "Level 2 Charging (200-240 Volts)",
    "Level 3 Quick Charging"
]


async def async_setup_entry(hass, entry, async_see):
    """Set up Leaf Spy based off an entry."""
    hass.data[DOMAIN]['context'].async_see = async_see
    hass.helpers.dispatcher.async_dispatcher_connect(
        DOMAIN, async_handle_message)
    return True


def _parse_see_args(message):
    """Parse the Leaf Spy parameters, into the format see expects."""
    dev_id = slugify('leaf_{}'.format(message['VIN']))
    args = {
        'dev_id': dev_id,
        'host_name': message['user'],
        'gps': (message['Lat'], message['Long']),
        'battery': float(message['SOC']),
        'attributes': {
            'amp_hours': float(message['AHr']),
            'trip': int(message['Trip']),
            'odometer': int(message['Odo']),
            'battery_temperature': float(message['BatTemp']),
            'outside_temperature': float(message['Amb']),
            'plug_state': PLUG_STATES[int(message['PlugState'])],
            'charge_mode': CHARGE_MODES[int(message['ChrgMode'])],
            'charge_power': int(message['ChrgPwr']),
            'vin': message['VIN'],
            'power_switch': message['PwrSw'] == '1',
            'device_battery': int(message['DevBat']),
            'rpm': int(message['RPM']),
            'gids': int(message['Gids']),
            'elevation': int(message['Elv']),
            'sequence': int(message['Seq']),
            ATTR_SOURCE_TYPE: SOURCE_TYPE_GPS
        }
    }

    return args


async def async_handle_message(hass, context, message):
    """Handle an Leaf Spy message."""
    _LOGGER.debug("Received %s", message)

    args = _parse_see_args(message)

    await context.async_see(**args)
