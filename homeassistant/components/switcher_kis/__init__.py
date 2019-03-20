"""Home Assistant Switcher Component.

For controlling the Switcher Boiler Device (https://www.switcher.co.il/).
Please follow configuring instructions here:
    https://www.home-assistant.io/components/switcher_kis/

Author: Tomer Figenblat
"""

from asyncio import TimeoutError as Asyncio_TimeoutError, wait_for
from datetime import datetime, timedelta
from functools import partial
from logging import getLogger
from typing import Dict, Optional

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_ICON, CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import (async_listen_platform,
                                             async_load_platform)
from homeassistant.helpers.event import async_call_later

_LOGGER = getLogger(__name__)

REQUIREMENTS = ['aioswitcher==2019.3.21']
DOMAIN = 'switcher_kis'
ENTITY_ID_FORMAT = DOMAIN + '_{}'

CONF_AUTO_OFF = 'auto_off'
CONF_DAYS = 'days'
CONF_DEVICE_ID = 'device_id'
CONF_DEVICE_PASSWORD = 'device_password'
CONF_END_TIME = 'end_time'
CONF_INCLUDE_SCHEDULE_SENSORS = 'include_schedule_sensors'
CONF_PHONE_ID = 'phone_id'
CONF_RECURRING = 'recurring'
CONF_SCHEDULE_ID = 'schedule_id'
CONF_SCHEDULE_SCAN_INTERVAL = 'schedules_scan_interval'
CONF_START_TIME = 'start_time'

DEFAULT_NAME = 'boiler'
DEFAULT_SCHEDULES_SCAN_INTERVAL = timedelta(minutes=5)

SWITCHER_MAX_SCHEDULES = 8

DISCOVERY_CONFIG = 'config'
DISCOVERY_DEVICE = 'device'
DISCOVERY_IP_ADDRESS = 'ip_address'
DISCOVERY_SCHEDULES = 'schedules'

EVENT_SWITCHER_DEVICE_UPDATED = 'switcher_device_update'
UPDATED_DEVICE = 'updated_device'

STATE_NOT_CONFIGURED = "Not configured"
STATE_NOT_ENABLED = "Not enabled"
STATE_NOT_RUNNING = "Not running"

ATTR_AUTO_OFF_SET = 'auto_off_set'
ATTR_DAYS = 'days'
ATTR_DEVICE_NAME = 'device_name'
ATTR_DURATION = 'duration'
ATTR_ELECTRIC_CURRNET = 'electric_current'
ATTR_ENABLED = 'enabled'
ATTR_END_TIME = 'end_time'
ATTR_IP_ADDRESS = 'ip_address'
ATTR_LAST_DATA_UPDATE = 'last_data_update'
ATTR_LAST_STATE_CHANGE = 'last_state_change'
ATTR_RECURRING = 'recurring'
ATTR_REMAINING_TIME = 'remaining_time'
ATTR_SCHEDULE_ID = 'schedule_id'
ATTR_START_TIME = 'start_time'

SERVICE_CREATE_SCHEDULE = 'create_schedule'
SERVICE_DELETE_SCHEDULE = 'delete_schedule'
SERVICE_DISABLE_SCHEDULE = 'disable_schedule'
SERVICE_ENABLE_SCHEDULE = 'enable_schedule'
SERVICE_SET_AUTO_OFF = 'set_auto_off'
SERVICE_TURN_ON_15 = 'turn_on_15_minutes'
SERVICE_TURN_ON_30 = 'turn_on_30_minutes'
SERVICE_TURN_ON_45 = 'turn_on_45_minutes'
SERVICE_TURN_ON_60 = 'turn_on_60_minutes'
SERVICE_UPDATE_DEVICE_NAME = 'update_device_name'
SERVICE_UPDATE_SCHEDULES = 'update_schedules'

# Do not edit the DAY_% values, they must match the ones in aioswitcher.consts
DAY_FRIDAY = "Friday"
DAY_MONDAY = "Monday"
DAY_SATURDAY = "Saturday"
DAY_SUNDAY = "Sunday"
DAY_THURSDAY = "Thursday"
DAY_TUESDAY = "Tuesday"
DAY_WEDNESDAY = "Wednesday"

SET_AUTO_OFF_SERVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_AUTO_OFF): cv.time_period_str
})

UPDATE_DEVICE_NAME_SERVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): vol.All(
        cv.string, vol.Length(min=2, max=32))
})

MANAGE_SCHEDULE_SERVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_SCHEDULE_ID): vol.All(
        cv.positive_int, vol.Range(min=0, max=7))
})

CREATE_RECURRING_SCHEDULE_SERVICE_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_START_TIME): cv.time_period_str,
    vol.Required(CONF_END_TIME): cv.time_period_str,
    vol.Required(CONF_RECURRING): vol.All(cv.boolean, True),
    vol.Optional(CONF_DAYS, default=[]): vol.All(
        cv.ensure_list_csv, [vol.In([DAY_MONDAY, DAY_TUESDAY, DAY_WEDNESDAY,
                                     DAY_THURSDAY, DAY_FRIDAY, DAY_SATURDAY,
                                     DAY_SUNDAY])]
    )
}))

CREATE_NON_RECURRING_SCHEDULE_SERVICE_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_START_TIME): cv.time_period_str,
    vol.Required(CONF_END_TIME): cv.time_period_str,
    vol.Required(CONF_RECURRING): vol.All(cv.boolean, False),
    vol.Optional(CONF_DAYS, default=[]): vol.Any(
        cv.match_all, None)
}))

CREATE_SCHEDULE_SERVICE_SCHEMA = vol.Any(
    CREATE_RECURRING_SCHEDULE_SERVICE_SCHEMA,
    CREATE_NON_RECURRING_SCHEDULE_SERVICE_SCHEMA)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PHONE_ID): cv.string,
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_DEVICE_PASSWORD): cv.string,
        vol.Optional(CONF_NAME,
                     default=DEFAULT_NAME): cv.slugify,
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
    from aioswitcher.bridge import SwitcherV2Bridge
    from aioswitcher.api import SwitcherV2Api

    phone_id = config[DOMAIN][CONF_PHONE_ID]
    device_id = config[DOMAIN][CONF_DEVICE_ID]
    device_password = config[DOMAIN][CONF_DEVICE_PASSWORD]
    include_sensors = config[DOMAIN][CONF_INCLUDE_SCHEDULE_SENSORS]

    async def async_switch_platform_discoverd(
            ip_addr: str, platform: str,
            discovery_info: Optional[Dict]) -> None:
        """Use for registering services after switch platform is discoverd."""
        async def async_switcher_control_service(service: ServiceCall) -> None:
            """Use for handling control service calls."""
            from aioswitcher.consts import COMMAND_ON

            timer = (''.join(list(filter(
                str.isdigit, service.service))))

            async with SwitcherV2Api(hass.loop, ip_addr, phone_id,
                                     device_id, device_password) as swapi:
                await swapi.control_device(COMMAND_ON, timer)

            return None

        for service in [SERVICE_TURN_ON_15, SERVICE_TURN_ON_30,
                        SERVICE_TURN_ON_45, SERVICE_TURN_ON_60]:
            hass.services.async_register(
                DOMAIN, service, async_switcher_control_service, schema={})

        async def async_set_auto_off_service(service: ServiceCall) -> None:
            """Use for handling setting device auto-off service calls."""
            async with SwitcherV2Api(hass.loop, ip_addr, phone_id,
                                     device_id, device_password) as swapi:
                await swapi.set_auto_shutdown(service.data[CONF_AUTO_OFF])

            return None

        hass.services.async_register(
            DOMAIN, SERVICE_SET_AUTO_OFF,
            async_set_auto_off_service,
            schema=SET_AUTO_OFF_SERVICE_SCHEMA)

        async def async_update_name_service(service: ServiceCall) -> None:
            """Use for handling update device name service calls."""
            async with SwitcherV2Api(hass.loop, ip_addr, phone_id,
                                     device_id, device_password) as swapi:
                await swapi.set_device_name(service.data[CONF_NAME])

            return None

        hass.services.async_register(
            DOMAIN, SERVICE_UPDATE_DEVICE_NAME,
            async_update_name_service,
            schema=UPDATE_DEVICE_NAME_SERVICE_SCHEMA)

    v2bridge = SwitcherV2Bridge(
        hass.loop, phone_id, device_id, device_password)

    await v2bridge.start()

    async def async_stop_bridge(event: Event) -> None:
        """On homeassistant stop, gracefully stop the bridge if running."""
        await v2bridge.stop()
        return None

    hass.async_add_job(hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, async_stop_bridge))

    try:
        device_data = await wait_for(
            v2bridge.queue.get(), timeout=5.0, loop=hass.loop)
    except (Asyncio_TimeoutError, RuntimeError):
        _LOGGER.exception("failed to get queue")
        return False

    async_listen_platform(
        hass,
        SWITCH_DOMAIN,
        partial(async_switch_platform_discoverd, device_data.ip_addr))

    hass.data[DOMAIN] = {
        DISCOVERY_CONFIG: config[DOMAIN],
        DISCOVERY_DEVICE: device_data
    }

    await hass.async_create_task(async_load_platform(
        hass, SWITCH_DOMAIN, DOMAIN, None, config))

    async def device_updates(timestamp: Optional[datetime]) -> None:
        """Use for updating the device data from the queue."""
        if v2bridge.running:
            device_new_data = await v2bridge.queue.get()
            if device_new_data:
                hass.bus.async_fire(EVENT_SWITCHER_DEVICE_UPDATED,
                                    {UPDATED_DEVICE: device_new_data})
            async_call_later(hass, 3, device_updates)
        return None

    async_call_later(hass, 3, device_updates)

    if include_sensors:
        async with SwitcherV2Api(hass.loop, device_data.ip_addr, phone_id,
                                 device_id, device_password) as swapi:
            schedules_response = await swapi.get_schedules()

        if schedules_response and schedules_response.found_schedules:
            hass.data[DOMAIN][DISCOVERY_IP_ADDRESS] = device_data.ip_addr
            hass.data[DOMAIN][DISCOVERY_SCHEDULES] = \
                schedules_response.get_schedules

            await hass.async_create_task(async_load_platform(
                hass, SENSOR_DOMAIN, DOMAIN, None, config))

    return True
