"""Home Assistant Switcher Component.

For controlling the Switcher Boiler Device (https://www.switcher.co.il/).
Please follow configuring instructions here:
    https://www.home-assistant.io/components/switcher_kis/

Author: Tomer Figenblat

This script is meant for internal use only.
Use it for creating and configuring the component.
"""

from asyncio import TimeoutError as AsyncioTimeoutError
from asyncio import wait_for
from datetime import datetime, timedelta
from logging import getLogger
from traceback import format_exc
from typing import Any, Dict, List, Optional  # noqa F401

import voluptuous as vol
from aioswitcher.bridge import SwitcherV2Thread
from aioswitcher.consts import (COMMAND_ON, DAYS_INT_DICT, FRIDAY, MONDAY,
                                SATURDAY, SCHEDULE_CREATE_DATA_FORMAT, SUNDAY,
                                THURSDAY, TUESDAY, WEDNESDAY)
from aioswitcher.devices import SwitcherV2Device
from aioswitcher.schedules import SwitcherV2Schedule  # noqa F401
from aioswitcher.swapi import (create_schedule, get_schedules,
                               send_command_to_device, set_auto_off_to_device,
                               update_name_of_device)
from aioswitcher.tools import (create_weekdays_value,
                               timedelta_str_to_schedule_time)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (CONF_NAME, EVENT_HOMEASSISTANT_STOP,
                                 SERVICE_TURN_OFF, SERVICE_TURN_ON)
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import (async_listen_platform,
                                             async_load_platform)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from . import CONF_SCHEDULE_SCAN_INTERVAL, DOMAIN

DEPENDENCIES = ['switcher_kis']

_LOGGER = getLogger(__name__)

SERVICE_TURN_ON_15 = 'turn_on_15_minutes'
SERVICE_TURN_ON_30 = 'turn_on_30_minutes'
SERVICE_TURN_ON_45 = 'turn_on_45_minutes'
SERVICE_TURN_ON_60 = 'turn_on_60_minutes'

CONF_AUTO_OFF = 'auto_off'
CONF_SCHEDULE_ID = 'schedule_id'
CONF_RECURRING = 'recurring'
CONF_START_TIME = 'start_time'
CONF_END_TIME = 'end_time'
CONF_DAYS = 'days'

DEFAULT_CONF_DAYS = []  # type: List[str]

DISCOVERY_CONFIG = 'config'
DISCOVERY_DEVICE = 'device'
DISCOVERY_SCHEDULES = 'schedules'

SERVICE_SET_AUTO_OFF = 'set_auto_off'
SET_AUTO_OFF_SERVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_AUTO_OFF): cv.time_period_str
})

SERVICE_UPDATE_DEVICE_NAME = 'update_device_name'
UPDATE_DEVICE_NAME_SERVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): vol.All(
        cv.string, vol.Length(min=2, max=32))
})


SERVICE_DELETE_SCHEDULE = 'delete_schedule'
SERVICE_ENABLE_SCHEDULE = 'enable_schedule'
SERVICE_DISABLE_SCHEDULE = 'disable_schedule'
MANAGE_SCHEDULE_SERVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_SCHEDULE_ID): vol.All(
        cv.positive_int, vol.Range(min=0, max=7))
})

SERVICE_CREATE_SCHEDULE = 'create_schedule'
CREATE_RECURRING_SCHEDULE_SERVICE_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_START_TIME): cv.time_period_str,
    vol.Required(CONF_END_TIME): cv.time_period_str,
    vol.Required(CONF_RECURRING): vol.All(cv.boolean, True),
    vol.Optional(CONF_DAYS, default=DEFAULT_CONF_DAYS): vol.All(
        cv.ensure_list_csv, [vol.In([MONDAY, TUESDAY, WEDNESDAY,
                                     THURSDAY, FRIDAY, SATURDAY, SUNDAY])]
        )
}))

CREATE_NON_RECURRING_SCHEDULE_SERVICE_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_START_TIME): cv.time_period_str,
    vol.Required(CONF_END_TIME): cv.time_period_str,
    vol.Required(CONF_RECURRING): vol.All(cv.boolean, False),
    vol.Optional(CONF_DAYS, default=DEFAULT_CONF_DAYS): vol.Any(
        cv.match_all, None)
}))

CREATE_SCHEDULE_SERVICE_SCHEMA = vol.Any(
    CREATE_RECURRING_SCHEDULE_SERVICE_SCHEMA,
    CREATE_NON_RECURRING_SCHEDULE_SERVICE_SCHEMA)


SWITCH_ENTITY = None  # type: Any
SENSOR_ENTITIES = {}  # type: Dict[str, SwitcherV2Schedule]


async def async_register_switch_entity(switch_created: SwitchDevice) -> None:
    """Use for registering the switch entity for data updates."""
    global SWITCH_ENTITY
    SWITCH_ENTITY = switch_created


async def async_register_sensor_entities(sensors_created: Dict[str, Entity]) \
        -> None:
    """Use for registering the sensor entity for data updates."""
    global SENSOR_ENTITIES
    SENSOR_ENTITIES = sensors_created


async def async_reg_services_platforms(
        hass: HomeAssistant, config: Dict, phone_id: str, device_id: str,
        device_password: str, include_sensors: bool,
        schedules_scan_interval: timedelta) -> None:
    """Use for registering HA's services and listen for platforms."""
    async def async_update_device_cb(device_data: SwitcherV2Device) -> None:
        """Use this as callback for updating the switcher entity.

        Called by the bridge thread on recursive broadcast message.
        """
        if SWITCH_ENTITY:
            await SWITCH_ENTITY.async_update_data(device_data)

        return None

    async def async_initial_data_cb(device_data: SwitcherV2Device) -> None:
        """Use this as callback for creating home assistant's entities.

        Called by the bridge thread on initial device discovery.
        """
        discovery_info = {
            DISCOVERY_CONFIG: config[DOMAIN],
            DISCOVERY_DEVICE: device_data
        }

        # CONF_SCHEDULE_SCAN_INTERVAL is a timedelta and not serializable.
        discovery_info[DISCOVERY_CONFIG].pop(CONF_SCHEDULE_SCAN_INTERVAL, None)

        await hass.async_create_task(
            async_load_platform(
                hass, SWITCH_DOMAIN, DOMAIN, discovery_info, config))

        if include_sensors:
            response = await get_schedules(device_data.ip_addr, phone_id,
                                           device_id, device_password)

            if response.found_schedules:
                discovery_info[DISCOVERY_SCHEDULES] = response.get_schedules

            await hass.async_create_task(
                async_load_platform(
                    hass, SENSOR_DOMAIN, DOMAIN, discovery_info,
                    config))

            async_track_time_interval(hass,
                                      async_update_schedules_data,
                                      schedules_scan_interval)

        return None

    async def async_update_schedules_data(timestamp: Optional[datetime]) \
            -> None:
        """Update the schedules data."""
        if SWITCH_ENTITY:
            response = await get_schedules(
                SWITCH_ENTITY.device_ip_addr, phone_id,
                device_id, device_password)

            if response.found_schedules and SENSOR_ENTITIES:
                updated_entities = []  # type: List[SwitcherV2Schedule]

                for schedule in response.get_schedules:
                    current_entity = SENSOR_ENTITIES[schedule.schedule_id]

                    await current_entity.async_update_schedule(schedule)

                    updated_entities.append(current_entity)

                for entity in SENSOR_ENTITIES.values():
                    if entity not in updated_entities:
                        await entity.async_deconfigure_schedule()

                updated_entities = []

        return None

    async def async_switch_platform_discoverd(platform: str,
                                              discovery_info: Optional[Dict]
                                              ) -> None:
        """Use for registering services after switch platform discoverd."""
        async def async_switcher_control_service(service: ServiceCall) -> None:
            """Use for handling control service calls."""
            if SWITCH_ENTITY:
                if service.service in [SERVICE_TURN_ON, SERVICE_TURN_OFF]:
                    if service.service == SERVICE_TURN_ON:
                        await SWITCH_ENTITY.async_turn_on()
                    else:
                        await SWITCH_ENTITY.async_turn_off()
                else:
                    timer = (''.join(list(filter(
                        str.isdigit, service.service))))

                    await send_command_to_device(
                        SWITCH_ENTITY.device_ip_addr, phone_id, device_id,
                        device_password, COMMAND_ON, timer)
            return None

        async def async_set_auto_off_service(service: ServiceCall) -> None:
            """Use for handling setting device auto-off service calls."""
            if SWITCH_ENTITY:
                await set_auto_off_to_device(
                    SWITCH_ENTITY.device_ip_addr, phone_id, device_id,
                    device_password, service.data[CONF_AUTO_OFF])

            return None

        async def async_update_name_service(service: ServiceCall) -> None:
            """Use for handling update device name service calls."""
            if SWITCH_ENTITY:
                await update_name_of_device(
                    SWITCH_ENTITY.device_ip_addr, phone_id, device_id,
                    device_password, service.data[CONF_NAME])

            return None

        for service in [SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TURN_ON_15,
                        SERVICE_TURN_ON_30, SERVICE_TURN_ON_45,
                        SERVICE_TURN_ON_60]:
            hass.services.async_register(
                DOMAIN, service, async_switcher_control_service, schema={})

        hass.services.async_register(
            DOMAIN, SERVICE_SET_AUTO_OFF,
            async_set_auto_off_service,
            schema=SET_AUTO_OFF_SERVICE_SCHEMA)

        hass.services.async_register(
            DOMAIN, SERVICE_UPDATE_DEVICE_NAME,
            async_update_name_service,
            schema=UPDATE_DEVICE_NAME_SERVICE_SCHEMA)

    async def async_sensor_platform_discovered(platform: str,
                                               discovery_info: Optional[Dict]
                                               ) -> None:
        """Use for registering services after switch platform discoverd."""
        async def async_create_schedule_service(service: ServiceCall) -> None:
            """Use for handling create schedule service calls."""
            recurring = service.data.get(CONF_RECURRING)
            if recurring and not service.data.get(CONF_DAYS):
                _LOGGER.error("A recursive schedule must contain %s",
                              "a list of days to run at")
            else:
                requested_days = [0]
                if recurring:
                    for day in service.data[CONF_DAYS]:
                        requested_days.append(DAYS_INT_DICT[day])

                weekdays = create_weekdays_value(requested_days)
                start_time = timedelta_str_to_schedule_time(
                    service.data[CONF_START_TIME])
                end_time = timedelta_str_to_schedule_time(
                    service.data[CONF_END_TIME])

                schedule_data = SCHEDULE_CREATE_DATA_FORMAT.format(
                    weekdays, start_time, end_time)

                if SWITCH_ENTITY:
                    response = await create_schedule(
                        SWITCH_ENTITY.device_ip_addr, phone_id, device_id,
                        device_password, schedule_data)

                    if response.successful and SENSOR_ENTITIES:
                        if response.found_schedules:
                            for schedule in response.get_schedules:
                                await SENSOR_ENTITIES[schedule.schedule_id] \
                                    .async_update_schedule(schedule)

            return None

        async def async_delete_schedule_service(service: ServiceCall) -> None:
            """Use for handling delete schedule service calls."""
            await SENSOR_ENTITIES[str(service.data[CONF_SCHEDULE_ID])] \
                .async_delete_schedule()
            return None

        async def async_ena_dis_schedule_service(service: ServiceCall) -> None:
            """Use for handling enable/disable of schedule service calls."""
            await SENSOR_ENTITIES[str(service.data[CONF_SCHEDULE_ID])] \
                .async_enable_disable_schedule(
                    service.service == SERVICE_ENABLE_SCHEDULE)
            return None

        hass.services.async_register(
            DOMAIN, SERVICE_CREATE_SCHEDULE,
            async_create_schedule_service,
            schema=CREATE_SCHEDULE_SERVICE_SCHEMA)

        hass.services.async_register(
            DOMAIN, SERVICE_DELETE_SCHEDULE,
            async_delete_schedule_service,
            schema=MANAGE_SCHEDULE_SERVICE_SCHEMA)

        for service_name in [SERVICE_ENABLE_SCHEDULE,
                             SERVICE_DISABLE_SCHEDULE]:
            hass.services.async_register(
                DOMAIN, service_name,
                async_ena_dis_schedule_service,
                schema=MANAGE_SCHEDULE_SERVICE_SCHEMA)

        return None

    v2bridge = None

    async def async_stop_bridge(event: Event) -> None:
        """On homeassistant stop event.

        Gracefully stop the bridge if running.
        """
        if v2bridge and v2bridge.running:
            try:
                v2bridge.join(timeout=2)
                await wait_for(v2bridge.stop(), timeout=1)
            except (RuntimeError, AsyncioTimeoutError):
                _LOGGER.error(
                    "Failed to gracefully stop switcher v2 bridge %s",
                    format_exc())

        return None

    # Register callback for switch discovery ended for the switch entity
    async_listen_platform(hass, SWITCH_DOMAIN,
                          async_switch_platform_discoverd)

    # Register callback for sensor discovery ended for the switch entity
    async_listen_platform(hass, SENSOR_DOMAIN,
                          async_sensor_platform_discovered)

    # Try to gracefully shutdown the bridge while stopping home assistant
    hass.async_add_job(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, async_stop_bridge))

    # Use 'thread_name' and 'is_daemon' arguments for setting up thread,
    # Defaults are: SwitcherV2Bridge and True.
    v2bridge = SwitcherV2Thread(
        phone_id, device_id, device_password, async_initial_data_cb,
        async_update_device_cb, hass.loop)

    # Start the thread which will schedule the callbacks on the event loop
    # The callbacks will be ran within HA's event loop as thread safe
    v2bridge.start()

    return None
