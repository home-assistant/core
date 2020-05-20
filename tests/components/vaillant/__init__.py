"""The tests for vaillant integration."""
import datetime
from unittest import mock

from asynctest import CoroutineMock, patch
from pymultimatic.model import (
    BoilerStatus,
    Circulation,
    Device,
    Dhw,
    HolidayMode,
    HotWater,
    OperatingModes,
    Report,
    Room,
    SettingModes,
    System,
    SystemInfo,
    TimePeriodSetting,
    TimeProgram,
    TimeProgramDay,
    Zone,
    ZoneHeating,
)
from pymultimatic.systemmanager import SystemManager

from homeassistant import config_entries
from homeassistant.components.vaillant import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.util import utcnow

from tests.common import async_fire_time_changed

VALID_MINIMAL_CONFIG = {CONF_USERNAME: "test", CONF_PASSWORD: "test"}


class SystemManagerMock(SystemManager):
    """Mock implementation of SystemManager."""

    instance = None
    system = None
    _methods = [f for f in dir(SystemManager) if not f.startswith("_")]

    @classmethod
    def reset_mock(cls):
        """Reset mock, clearing instance and system."""
        cls.instance = None
        cls.system = None

    def __init__(self, user, password, smart_phone_id, session, serial):
        """Mock the constructor."""
        self.system = self.__class__.system
        self._init()
        self.__class__.instance = self

    def _init(self):
        for method in self.__class__._methods:
            setattr(self, method, CoroutineMock())

        setattr(self, "get_system", CoroutineMock(return_value=self.system))

        get_zone = mock.MagicMock(
            return_value=lambda: self.system.zones[0]
            if self.system and self.system.zones
            else None
        )
        get_room = mock.MagicMock(
            return_value=lambda: self.system.rooms[0]
            if self.system and self.system.rooms
            else None
        )
        setattr(self, "get_zone", get_zone)
        setattr(self, "get_room", get_room)


def get_system():
    """Return default system."""
    boiler_status = BoilerStatus(
        "boiler",
        "short description",
        "S.31",
        "Long description",
        datetime.datetime.now(),
        "hint",
    )

    heating = ZoneHeating(
        time_program=time_program(SettingModes.NIGHT, None),
        operating_mode=OperatingModes.AUTO,
        target_low=22,
        target_high=30,
    )
    zone = Zone(
        id="zone_1",
        name="Zone 1",
        temperature=25,
        active_function="heating",
        rbr=False,
        heating=heating,
    )

    room_device = Device("Device 1", "123456789", "VALVE", False, False)
    room = Room(
        id="1",
        name="Room 1",
        time_program=time_program(),
        temperature=22,
        target_high=24,
        operating_mode=OperatingModes.AUTO,
        child_lock=False,
        window_open=False,
        devices=[room_device],
    )

    hot_water = HotWater(
        id="dhw",
        name="Hot water",
        time_program=time_program(temp=None),
        temperature=45,
        target_high=40,
        operating_mode=OperatingModes.AUTO,
    )

    circulation = Circulation(
        id="dhw",
        name="Circulation",
        time_program=time_program(temp=None),
        operating_mode=OperatingModes.AUTO,
    )
    dhw = Dhw(hotwater=hot_water, circulation=circulation)

    outdoor_temp = 18

    info = SystemInfo(
        "VR920",
        "666777888",
        "System name",
        "01:01:AA:CC:CC:CC",
        "01:01:AA:DD:DD:DD",
        "1.6.8",
        "ONLINE",
        "UPDATE_NOT_PENDING",
    )

    reports = [
        Report(
            device_name="VRC700 MultiMatic",
            device_id="Control_SYS_MultiMatic",
            unit="bar",
            value=1.9,
            name="Water pressure",
            id="WaterPressureSensor",
        )
    ]
    return System(
        holiday=HolidayMode(False),
        quick_mode=None,
        info=info,
        zones=[zone],
        rooms=[room],
        dhw=dhw,
        reports=reports,
        outdoor_temperature=outdoor_temp,
        boiler_status=boiler_status,
        errors=[],
        ventilation=None,
    )


def active_holiday_mode():
    """Return a active holiday mode."""
    start = datetime.date.today() - datetime.timedelta(days=1)
    end = datetime.date.today() + datetime.timedelta(days=1)
    return HolidayMode(True, start, end, 15)


def time_program(heating_mode=SettingModes.OFF, temp=20):
    """Create a default time program."""
    tp_day_setting = TimePeriodSetting("00:00", temp, heating_mode)
    tp_day = TimeProgramDay([tp_day_setting])
    tp_days = {
        "monday": tp_day,
        "tuesday": tp_day,
        "wednesday": tp_day,
        "thursday": tp_day,
        "friday": tp_day,
        "saturday": tp_day,
        "sunday": tp_day,
    }
    return TimeProgram(tp_days)


async def goto_future(hass, future=None):
    """Move to future."""
    if not future:
        future = utcnow() + datetime.timedelta(minutes=5)
    with mock.patch("homeassistant.util.utcnow", return_value=future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()


async def setup_vaillant(hass, config=None, system=None):
    """Set up vaillant component."""
    if not config:
        config = VALID_MINIMAL_CONFIG
    if not system:
        system = get_system()
    SystemManagerMock.system = system

    with patch(
        "homeassistant.components.vaillant.hub.ApiHub.authenticate", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=config
        )
    await hass.async_block_till_done()
    return result


async def call_service(hass, domain, service, data):
    """Call hass service."""
    await hass.services.async_call(domain, service, data)
    await hass.async_block_till_done()


def assert_entities_count(hass, count):
    """Count entities owned by the component."""
    assert (
        len(hass.states.async_entity_ids()) == len(hass.data[DOMAIN].entities) == count
    )
