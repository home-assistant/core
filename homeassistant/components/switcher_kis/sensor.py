"""Home Assistant Switcher Component Sensor platform.

For controlling the Switcher Boiler Device (https://www.switcher.co.il/).
Please follow configuring instructions here:
    https://www.home-assistant.io/components/switcher_kis/

Author: Tomer Figenblat
"""

from asyncio import Future
from logging import getLogger
from typing import Callable, Dict, List, Optional
from datetime import datetime

from homeassistant.components.sensor import ENTITY_ID_FORMAT as SENSOR_FORMAT
from homeassistant.const import CONF_ICON, CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from . import (
    ATTR_DAYS, ATTR_DURATION, ATTR_ENABLED, ATTR_END_TIME, ATTR_RECURRING,
    ATTR_SCHEDULE_ID, ATTR_START_TIME, CONF_DAYS, CONF_DEVICE_ID,
    CONF_DEVICE_PASSWORD, CONF_END_TIME, CONF_PHONE_ID, CONF_RECURRING,
    CONF_SCHEDULE_SCAN_INTERVAL, CONF_START_TIME,
    CREATE_SCHEDULE_SERVICE_SCHEMA, DISCOVERY_CONFIG, DISCOVERY_IP_ADDRESS,
    CONF_SCHEDULE_ID, DISCOVERY_SCHEDULES, DOMAIN,
    ENTITY_ID_FORMAT as SWITCHER_KIS_FORMAT, MANAGE_SCHEDULE_SERVICE_SCHEMA,
    SERVICE_CREATE_SCHEDULE, SERVICE_DELETE_SCHEDULE, SERVICE_DISABLE_SCHEDULE,
    SERVICE_ENABLE_SCHEDULE, SERVICE_UPDATE_SCHEDULES, STATE_NOT_CONFIGURED,
    STATE_NOT_ENABLED, STATE_NOT_RUNNING, SWITCHER_MAX_SCHEDULES)

_LOGGER = getLogger(__name__)

DEPENDENCIES = ['switcher_kis']
ENTITY_ID_FORMAT = SENSOR_FORMAT.format(SWITCHER_KIS_FORMAT)
SCHEDULE_NAME_FORMAT = "{} Schedule{}"


async def async_setup_platform(hass: HomeAssistant, config: Dict,
                               async_add_entities: Callable,
                               discovery_info: Optional[Dict]) -> None:
    """Set up the switcher platform for the sensor component."""
    from aioswitcher.consts import (DISABLE_SCHEDULE, ENABLE_SCHEDULE,
                                    SCHEDULE_CREATE_DATA_FORMAT,
                                    DAY_TO_INT_DICT)
    from aioswitcher.api import SwitcherV2Api
    # pylint: disable=unused-import
    from aioswitcher.api.messages import (
        SwitcherV2GetScheduleResponseMSG, SwitcherV2DeleteScheduleResponseMSG,
        SwitcherV2DisableEnableScheduleResponseMSG)
    # pylint: enable=unused-import
    from aioswitcher.tools import (create_weekdays_value,
                                   timedelta_str_to_schedule_time)

    if hass.data[DOMAIN][DISCOVERY_CONFIG]:
        name = hass.data[DOMAIN][DISCOVERY_CONFIG][CONF_NAME].title()
        icon = hass.data[DOMAIN][DISCOVERY_CONFIG].get(CONF_ICON)
        phone_id = hass.data[DOMAIN][DISCOVERY_CONFIG][CONF_PHONE_ID]
        device_id = hass.data[DOMAIN][DISCOVERY_CONFIG][CONF_DEVICE_ID]
        device_password = (
            hass.data[DOMAIN][DISCOVERY_CONFIG][CONF_DEVICE_PASSWORD])
        schedules_scan_interval = (
            hass.data[DOMAIN][DISCOVERY_CONFIG][CONF_SCHEDULE_SCAN_INTERVAL])

    else:
        raise PlatformNotReady("No config data found")

    if hass.data[DOMAIN][DISCOVERY_IP_ADDRESS]:
        ip_address = hass.data[DOMAIN][DISCOVERY_IP_ADDRESS]
    else:
        raise PlatformNotReady("No ip address recieved")

    sensors_created = {}  # type: Dict[str, SwitcherScheduleSensor]
    if hass.data[DOMAIN][DISCOVERY_SCHEDULES]:
        for schedule in hass.data[DOMAIN][DISCOVERY_SCHEDULES]:
            sensors_created[schedule.schedule_id] = \
                SwitcherScheduleSensor(
                    hass,
                    SCHEDULE_NAME_FORMAT.format(name, schedule.schedule_id),
                    icon,
                    schedule.schedule_id,
                    schedule)

        for i in range(0, SWITCHER_MAX_SCHEDULES):
            if str(i) not in sensors_created.keys():
                idx = str(i)
                sensors_created[idx] = \
                    SwitcherScheduleSensor(
                        hass,
                        SCHEDULE_NAME_FORMAT.format(name, idx),
                        icon,
                        idx)
    else:
        raise PlatformNotReady("No schedules discoverd")

    if sensors_created:
        async_add_entities(sensors_created.values(), False)

        async def _distribute_schedules_data(
                response: SwitcherV2GetScheduleResponseMSG) -> None:
            """Distribute the schedules data."""
            updated_schedule_id = []  # type: List[str]
            for schedule in response.get_schedules:
                updated_schedule_id.append(schedule.schedule_id)
                schedule.init_future.add_done_callback(
                    sensors_created[schedule.schedule_id].update_data)

            for j in range(0, SWITCHER_MAX_SCHEDULES):
                idx = str(j)
                if idx not in updated_schedule_id:
                    if sensors_created[idx].configured:
                        hass.async_create_task(
                            sensors_created[idx].async_deconfigure_schedule())
            return None

        async def _update_schedules_data() -> None:
            """Update the schedules data."""
            update_response = None  # type: SwitcherV2GetScheduleResponseMSG
            async with SwitcherV2Api(hass.loop, ip_address, phone_id,
                                     device_id, device_password) as swapi:
                update_response = await swapi.get_schedules()
                if update_response and update_response.successful:
                    hass.async_create_task(
                        _distribute_schedules_data(update_response))
            return None

        async def async_update_schedules_data_on_interval(
                timestamp: Optional[datetime]) -> None:
            """Use for handling time intervals update."""
            hass.async_create_task(_update_schedules_data())
            return None

        async_track_time_interval(
            hass, async_update_schedules_data_on_interval,
            schedules_scan_interval)

        async def async_update_schedules_data_service(
                service: ServiceCall) -> None:
            """Use for handling update schedules service calls."""
            hass.async_create_task(_update_schedules_data())
            return None

        hass.services.async_register(
            DOMAIN, SERVICE_UPDATE_SCHEDULES,
            async_update_schedules_data_service, schema={})

        async def async_delete_schedule_service(service: ServiceCall) -> None:
            """Use for handling delete schedule service calls."""
            schedule_id = str(service.data[CONF_SCHEDULE_ID])
            if not sensors_created[schedule_id].configured:
                _LOGGER.warning("schedule %s is not configured", schedule_id)
            else:
                response = None  # type: SwitcherV2DeleteScheduleResponseMSG
                async with SwitcherV2Api(hass.loop, ip_address, phone_id,
                                         device_id, device_password) as swapi:
                    response = await swapi.delete_schedule(schedule_id)

                if response and response.successful:
                    hass.async_create_task(
                        sensors_created[
                            schedule_id].async_deconfigure_schedule())

            return None

        hass.services.async_register(
            DOMAIN, SERVICE_DELETE_SCHEDULE,
            async_delete_schedule_service,
            schema=MANAGE_SCHEDULE_SERVICE_SCHEMA)

        async def async_ena_dis_schedule_service(service: ServiceCall) -> None:
            """Use for handling enable/disable of schedule service calls."""
            schedule_id = str(service.data[CONF_SCHEDULE_ID])
            schedule_details = sensors_created[schedule_id].schedule_details
            do_enable = service.service == SERVICE_ENABLE_SCHEDULE

            if do_enable and schedule_details.enabled:
                _LOGGER.warning("schedule %s is already enabled", schedule_id)
            elif not do_enable and not schedule_details.enabled:
                _LOGGER.warning("schedule %s is already disabled", schedule_id)
            else:
                schedule_data = (schedule_details.schedule_data[0:2]
                                 + (ENABLE_SCHEDULE if do_enable
                                    else DISABLE_SCHEDULE)
                                 + schedule_details.schedule_data[4:])

                response = \
                    None  # type: SwitcherV2DisableEnableScheduleResponseMSG
                async with SwitcherV2Api(hass.loop, ip_address, phone_id,
                                         device_id, device_password) as swapi:
                    response = await swapi.disable_enable_schedule(
                        schedule_data)

                if response and response.successful:
                    schedule_details.enabled = do_enable
                    schedule_details.schedule_data = schedule_data
                    hass.async_create_task(
                        sensors_created[schedule_id].async_set_next_run())

            return None

        for service_name in [SERVICE_ENABLE_SCHEDULE,
                             SERVICE_DISABLE_SCHEDULE]:
            hass.services.async_register(
                DOMAIN, service_name,
                async_ena_dis_schedule_service,
                schema=MANAGE_SCHEDULE_SERVICE_SCHEMA)

        async def async_create_schedule_service(service: ServiceCall) -> None:
            """Use for handling create schedule service calls."""
            recurring = service.data[CONF_RECURRING]
            if recurring and not service.data.get(CONF_DAYS):
                _LOGGER.error(
                    "A recursive schedule must specify days to run on.")
                return None

            requested_days = [0]
            if recurring:
                for day in service.data[CONF_DAYS]:
                    requested_days.append(DAY_TO_INT_DICT[day])
            weekdays = await create_weekdays_value(hass.loop, requested_days)

            start_time = await timedelta_str_to_schedule_time(
                hass.loop, service.data[CONF_START_TIME])

            end_time = await timedelta_str_to_schedule_time(
                hass.loop, service.data[CONF_END_TIME])

            schedule_data = SCHEDULE_CREATE_DATA_FORMAT.format(
                weekdays, start_time, end_time)

            async with SwitcherV2Api(hass.loop, ip_address, phone_id,
                                     device_id, device_password) as swapi:
                create_response = await swapi.create_schedule(schedule_data)
                if create_response and create_response.successful:
                    get_response = await swapi.get_schedules()
                    if get_response and get_response.successful:
                        hass.async_create_task(
                            _distribute_schedules_data(get_response))
            return None

        hass.services.async_register(
            DOMAIN, SERVICE_CREATE_SCHEDULE,
            async_create_schedule_service,
            schema=CREATE_SCHEDULE_SERVICE_SCHEMA)

    return None


class SwitcherScheduleSensor(Entity):
    """Home Assistant sensor entity."""

    from aioswitcher.schedules import SwitcherV2Schedule

    def __init__(
            self, hass: HomeAssistant, name: str, icon: str, schedule_id: str,
            schedule_details: SwitcherV2Schedule = None) -> None:
        """Initialize the entity."""
        self._hass = hass
        self._name = name
        self._icon = icon
        self._configured = False
        self._schedule_id = schedule_id
        self._next_run = STATE_NOT_RUNNING
        self._schedule_details = schedule_details
        if schedule_details:
            hass.async_create_task(self.async_set_next_run(True))

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        if not self._configured:
            return STATE_NOT_CONFIGURED
        if self._schedule_details and not self._schedule_details.enabled:
            return STATE_NOT_ENABLED
        return self._next_run

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def icon(self) -> str:
        """Return mdi icon."""
        return self._icon

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "{}-{}".format(self._name, self._schedule_id).strip()

    @property
    def schedule_id(self) -> str:
        """Return the schedule id."""
        return self._schedule_id

    @property
    def configured(self) -> bool:
        """Return true if the schedule is not configured."""
        return self._configured

    @property
    def schedule_details(self) -> 'SwitcherV2Schedule':
        """Return the SwitcherV2Schedule object."""
        return self._schedule_details

    @property
    def device_state_attributes(self) -> Optional[Dict]:
        """Return the state attributes."""
        attributes = {}
        attributes[ATTR_SCHEDULE_ID] = self.schedule_id
        if self._configured and self._schedule_details:
            attributes[ATTR_ENABLED] = self._schedule_details.enabled
            attributes[ATTR_RECURRING] = self._schedule_details.recurring
            attributes[ATTR_START_TIME] = self._schedule_details.start_time
            attributes[ATTR_END_TIME] = self._schedule_details.end_time
            attributes[ATTR_DURATION] = self._schedule_details.duration
            if self._schedule_details.recurring:
                attributes[ATTR_DAYS] = self._schedule_details.days

        return attributes

    async def async_deconfigure_schedule(self) -> None:
        """Deconfigure deleted schedules."""
        if self._configured:
            self._configured = False
            self._next_run = STATE_NOT_RUNNING
            self._schedule_details = None

            self.async_schedule_update_ha_state()

        return None

    def update_data(self, future: Future) -> None:
        """Update the entity data."""
        self._schedule_details = future.result()
        self._hass.async_create_task(self.async_set_next_run())

    async def async_set_next_run(self, setup_mode: bool = False) -> None:
        """Update the schedule data."""
        from aioswitcher.schedules import calc_next_run_for_schedule

        self._configured = True
        if self._schedule_details.enabled:
            self._next_run = await calc_next_run_for_schedule(
                self._hass.loop, self._schedule_details)
        else:
            self._next_run = STATE_NOT_RUNNING

        if not setup_mode:
            self.async_schedule_update_ha_state()

        return None
