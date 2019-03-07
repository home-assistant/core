"""Home Assistant Switcher Component.

For controlling the Switcher Boiler Device (https://www.switcher.co.il/).
Please follow configuring instructions here:
    https://www.home-assistant.io/components/switcher_kis/

Author: Tomer Figenblat

This cannot be configured as a sensor platform,
Please follow the instruction of configuring the switcher_kis component.
"""

from asyncio import wait_for, TimeoutError as AsyncioTimeoutError
from logging import getLogger
from typing import Any, Awaitable, Callable, Dict, List, Optional

from aioswitcher.consts import DISABLE_SCHEDULE, ENABLE_SCHEDULE
from aioswitcher.devices import SwitcherV2Device
from aioswitcher.schedules import (SwitcherV2Schedule,
                                   calc_next_run_for_schedule)
from aioswitcher.swapi import delete_schedule, disable_enable_schedule

from homeassistant.components.sensor import ENTITY_ID_FORMAT as SENSOR_FORMAT
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_ICON, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity, async_generate_entity_id

from . import ENTITY_ID_FORMAT as SWITCHER_KIS_FORMAT
from ._service_registration import (
    DISCOVERY_CONFIG, DISCOVERY_DEVICE, DISCOVERY_SCHEDULES,
    async_register_sensor_entities)

DEPENDENCIES = ['switcher_kis']

_LOGGER = getLogger(__name__)

ENTITY_ID_FORMAT = SENSOR_FORMAT.format(SWITCHER_KIS_FORMAT)

STATE_NOT_ENABLED = "Not enabled"
STATE_NOT_CONFIGURED = "Not configured"
STATE_NOT_RUNNING = "Not running"

SCHEDULE_NAME_FORMAT = '{}_schedule{}'
SCHEDULE_FRIENDLY_NAME_FORMAT = "{} Schedule {}"

ATTR_ENABLED = 'enabled'
ATTR_RECURRING = 'recurring'
ATTR_START_TIME = 'start_time'
ATTR_END_TIME = 'end_time'
ATTR_DURATION = 'duration'
ATTR_DAYS = 'days'
ATTR_CONFIGURED = 'configured'
ATTR_SCHEDULE_ID = 'schedule_id'


async def async_setup_platform(hass: HomeAssistant, config: Dict,
                               async_add_entities: Callable,
                               discovery_info: Dict) -> None:
    """Set up the switcher platform for the sensor component."""
    if discovery_info.get(DISCOVERY_CONFIG):
        name = str(discovery_info[DISCOVERY_CONFIG].get(CONF_NAME))

        friendly_name = discovery_info[DISCOVERY_CONFIG].get(
            CONF_FRIENDLY_NAME, name.title())

        icon = discovery_info[DISCOVERY_CONFIG].get(CONF_ICON)

    else:
        raise PlatformNotReady("No config data found")

    if discovery_info.get(DISCOVERY_DEVICE):
        sensors_created = []   # type: List[Entity]
        device = discovery_info.get(DISCOVERY_DEVICE)  # type: SwitcherV2Device
        sensors_for_register = {}  # type: Dict[str, Entity]

        for i in range(8):
            idx = str(i)
            entity_created = SwitcherScheduleSensor(
                hass, SCHEDULE_NAME_FORMAT.format(name, idx),
                SCHEDULE_FRIENDLY_NAME_FORMAT.format(friendly_name, idx),
                icon, device.ip_addr, device.phone_id, device.device_id,
                device.device_password, idx)

            if discovery_info.get(DISCOVERY_SCHEDULES):
                for schedule in discovery_info[DISCOVERY_SCHEDULES]:
                    if schedule.schedule_id == idx:
                        await entity_created.async_update_schedule(
                            schedule, True)
                        break

            sensors_created.append(entity_created)
            sensors_for_register[idx] = entity_created

    else:
        raise PlatformNotReady("No device data discoverd")

    async_add_entities(sensors_created, False)

    try:
        await wait_for(async_register_sensor_entities(sensors_for_register),
                       timeout=1)

    except AsyncioTimeoutError:
        raise PlatformNotReady("Unable to register for data updates")

    return None


class SwitcherScheduleSensor(Entity):
    """Representation of the schedule sensor entity."""

    def __init__(self, hass: HomeAssistant, name: str, friendly_name: str,
                 icon: str, ip_addr: str, phone_id: str, device_id: str,
                 device_password: str, schedule_id: str) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._ip_addr = ip_addr
        self._phone_id = phone_id
        self._device_id = device_id
        self._device_password = device_password
        self._schedule_id = schedule_id
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, name, hass=hass)
        self._name = friendly_name
        self._icon = icon
        self._configured = False
        self._schedule_details = None  # type: Optional[SwitcherV2Schedule]
        self._next_run = STATE_NOT_RUNNING

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
    def schedule_id(self) -> str:
        """Return the schedule id."""
        return self._schedule_id

    @property
    def state_attributes(self) -> Optional[Dict]:
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

            await self._hass.async_create_task(self.async_update_ha_state())

        return None

    async def async_enable_disable_schedule(self, do_enable: bool = True) \
            -> None:
        """Enable or disable the schedule."""
        if self._schedule_details:
            if do_enable and self._schedule_details.enabled:
                _LOGGER.warning("schedule %s %s", self.schedule_id,
                                "is already enabled")
            elif not do_enable and not self._schedule_details.enabled:
                _LOGGER.warning("schedule %s %s", self.schedule_id,
                                "is already disabled")
            else:
                schedule_data = (self._schedule_details.schedule_data[0:2]
                                 + (ENABLE_SCHEDULE if do_enable
                                    else DISABLE_SCHEDULE)
                                 + self._schedule_details.schedule_data[4:])

                response = await disable_enable_schedule(
                    self._ip_addr, self._phone_id, self._device_id,
                    self._device_password, schedule_data)

                if response.successful:
                    self._schedule_details.enabled = do_enable
                    self._schedule_details.schedule_data = schedule_data
                    if do_enable:
                        self._next_run = calc_next_run_for_schedule(
                            self._schedule_details)
                    else:
                        self._next_run = STATE_NOT_RUNNING

                    await self._hass.async_create_task(
                        self.async_update_ha_state())

        return None

    async def async_delete_schedule(self) -> Optional[Awaitable[Any]]:
        """Delete the schedule."""
        if not self._configured:
            _LOGGER.warning("schedule %s %s", self._schedule_id,
                            "is not configured")
        else:
            response = await delete_schedule(
                self._ip_addr, self._phone_id, self._device_id,
                self._device_password, self.schedule_id)

            if response.successful:
                return await self.async_deconfigure_schedule()

        return None

    async def async_update_schedule(
            self, schedule_details: SwitcherV2Schedule,
            in_setup: bool = False) -> None:
        """Update the schedule data."""
        self._configured = True
        self._schedule_details = schedule_details
        if self._schedule_details.enabled:
            self._next_run = calc_next_run_for_schedule(
                self._schedule_details)
        else:
            self._next_run = STATE_NOT_RUNNING

        if not in_setup:
            await self._hass.async_create_task(self.async_update_ha_state())

        return None
