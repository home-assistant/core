"""Home Assistant Switcher Component.

For controlling the Switcher Boiler Device (https://www.switcher.co.il/).
Please follow configuring instructions here:
    https://www.home-assistant.io/components/switcher_kis/

Author: Tomer Figenblat

Example yaml configuration,
Get you device details using the instructions here:
https://github.com/NightRang3r/Switcher-V2-Python.

Mandatory only configuration:
switcher_kis:
  phone_id: 'xxxx'
  device_id: 'xxxxxx'
  device_password: 'xxxxxxxx'

Full configuration:
switcher_kis:
  phone_id: 'xxxx'
  device_id: 'xxxxxx'
  device_password: 'xxxxxxxx'
  name: 'my_boiler'
  friendly_name: "My Friendly Boiler"
  icon: 'mdi:my-icon'
  include_schedule_sensors: true
  schedules_scan_interval:
    minutes: 5

Defaults:
name = 'boiler'
friendly_name = 'Boiler'
include_sensors = false
schedules_scan_interval = {'mintues': 5}

The minimal configuration will:
- Create 1 switch entity called Boiler with the entity id:
  switch.switcher_kis_boiler.
- Register the following services:
  - switcher_kis.turn_on - no arguments needed.
  - switcher_kis.turn_off - no arguments needed.
  - switcher_kis.turn_on_15_minutes - no arguments needed.
  - switcher_kis.turn_on_30_minutes - no arguments needed.
  - switcher_kis.turn_on_45_minutes - no arguments needed.
  - switcher_kis.turn_on_60_minutes - no arguments needed.
  - switcher_kis.set_auto_off - takes 1 string argument {'auto_off': '01:30'}
  - switcher_kis.update_device_name - takes 1 string argument {'name': 'boil'}

Setting the 'include_schedule_sensors' key to True,
Will result in all the above plus the following:
- Creation of 8 sensors entities represnting the device's schedules (0-7),
  The names will be constructed from the 'name' key '_schedule' and the id,
  The same goes for the friendly names:
  - sensor.switcher_kis_boiler_schedule0: Boiler Schedule 0
  ...
  - sensor.switcher_kis_boiler_schedule7: Boiler Schedule 7

  The sensors state will allways provide the minumum information:
  - Not configured
  - Not enabled
  - Due today at 17:30
  - Due tommorow at 20:00

- Register the following services:
  - switcher_kis.create_schedule - takes the following mandatory arguments:
    {'start_time': '19:30', 'end_time': '20:30', 'recurring': false}
    if recurring is set to true, you must provide an extra argument:
    {'days': ['Monday', 'Wednesday', 'Saturday']}
  - switcher_kis.delete_schedule - takes 1 int argument {'schedule_id': 3'}
  - switcher_kis.enable_schedule - takes 1 int argument {'schedule_id': 0'}
  - switcher_kis.disable_schedule - takes 1 int argument {'schedule_id': 7'}

"""

from logging import getLogger
from typing import Dict
from traceback import format_exc
from datetime import timedelta

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_ICON, CONF_NAME
from homeassistant.helpers import config_validation as cv


REQUIREMENTS = ['aioswitcher==2019.2.6']

_LOGGER = getLogger(__name__)

DOMAIN = 'switcher_kis'
ENTITY_ID_FORMAT = DOMAIN + '_{}'

CONF_PHONE_ID = 'phone_id'
CONF_DEVICE_ID = 'device_id'
CONF_DEVICE_PASSWORD = 'device_password'
CONF_INCLUDE_SCHEDULE_SENSORS = 'include_schedule_sensors'
CONF_SCHEDULE_SCAN_INTERVAL = 'schedules_scan_interval'

DEFAULT_NAME = 'boiler'
DEFAULT_SCHEDULES_SCAN_INTERVAL = timedelta(minutes=5)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PHONE_ID): cv.string,
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_DEVICE_PASSWORD): cv.string,
        vol.Optional(CONF_NAME,
                     default=DEFAULT_NAME): cv.slugify,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_ICON): cv.icon,
        vol.Optional(CONF_INCLUDE_SCHEDULE_SENSORS,
                     default=False): cv.boolean,
        vol.Optional(CONF_SCHEDULE_SCAN_INTERVAL,
                     default=DEFAULT_SCHEDULES_SCAN_INTERVAL): vol.All(
                         cv.time_period, cv.positive_timedelta)
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the switcher component."""
    from ._service_registration import async_reg_services_platforms

    phone_id = config[DOMAIN].get(CONF_PHONE_ID)
    device_id = config[DOMAIN].get(CONF_DEVICE_ID)
    device_password = config[DOMAIN].get(CONF_DEVICE_PASSWORD)
    include_sensors = config[DOMAIN].get(CONF_INCLUDE_SCHEDULE_SENSORS)
    schedules_scan_interval = config[DOMAIN].get(CONF_SCHEDULE_SCAN_INTERVAL)

    if None in [phone_id, device_id, device_password]:
        _LOGGER.error("No details for device connection supplied")
        return False

    try:
        # Create the bridge, Listen to platforms and register services
        await async_reg_services_platforms(
            hass, config, phone_id, device_id, device_password,
            include_sensors, schedules_scan_interval)

    except RuntimeError:
        _LOGGER.error("Failed to load component %s", format_exc())
        return False

    return True
