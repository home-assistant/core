"""Api hub and integration data."""
import logging

from pymultimatic.api import ApiError
from pymultimatic.model import (
    Circulation,
    HolidayMode,
    HotWater,
    OperatingModes,
    QuickModes,
    QuickVeto,
    Room,
    System,
    Zone,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.util import Throttle

from .const import (
    DEFAULT_QUICK_VETO_DURATION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SMART_PHONE_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ApiHub:
    """Vaillant entry point for home-assistant."""

    def __init__(self, hass, username, password, serial):
        """Initialize hub."""
        # pylint: disable=import-outside-toplevel
        from pymultimatic.systemmanager import SystemManager

        session = async_create_clientsession(hass)
        self._manager = SystemManager(
            username, password, session, DEFAULT_SMART_PHONE_ID, serial
        )
        self.system: System = None
        self.update_system = Throttle(DEFAULT_SCAN_INTERVAL)(self._update_system)
        self._hass = hass

    async def authenticate(self):
        """Try to authenticate to the API."""
        try:
            return await self._manager.login(True)
        except ApiError as err:
            await self._handle_api_error(err)
            return False

    async def request_hvac_update(self):
        """Request is not on the classic update since it won't fetch data.

        The request update will trigger something at vaillant API and it will
        ask data to your system.
        """
        try:
            _LOGGER.debug("Will request_hvac_update")
            await self._manager.request_hvac_update()
        except ApiError as err:
            if err.response.status == 409:
                _LOGGER.warning("request_hvac_update is done too often")
            else:
                await self._handle_api_error(err)
                await self.authenticate()

    async def _update_system(self):
        """Fetch vaillant system."""

        try:
            self.system = await self._manager.get_system()
            _LOGGER.debug("update_system successfully fetched")
        except ApiError as err:
            # update_system is called by all entities, if it fails for
            # one entity, it will certainly fail for others.
            # catching exception so the throttling is occurring
            await self._handle_api_error(err)
            await self.authenticate()

    async def logout(self):
        """Logout from API."""

        try:
            await self._manager.logout()
        except ApiError:
            _LOGGER.warning("Cannot logout from vaillant API", exc_info=True)
            return False
        return True

    async def _handle_api_error(self, api_err):
        resp = await api_err.response.json()
        _LOGGER.exception(
            "Unable to fetch data from vaillant, API says: %s, status: %s",
            resp,
            api_err.response.status,
        )

    def find_component(self, comp):
        """Find a component in the system with the given id, no IO is done."""

        if isinstance(comp, Zone):
            for zone in self.system.zones:
                if zone.id == comp.id:
                    return zone
        if isinstance(comp, Room):
            for room in self.system.rooms:
                if room.id == comp.id:
                    return room
        if isinstance(comp, HotWater):
            if self.system.dhw.hotwater and self.system.dhw.hotwater.id == comp.id:
                return self.system.dhw.hotwater
        if isinstance(comp, Circulation):
            if (
                self.system.dhw.circulation
                and self.system.dhw.circulation.id == comp.id
            ):
                return self.system.dhw.circulation

        return None

    async def set_hot_water_target_temperature(self, entity, target_temp):
        """Set hot water target temperature.

        * If there is a quick mode that impact dhw running on or holiday mode,
        remove it.

        * If dhw is ON or AUTO, modify the target temperature

        * If dhw is OFF, change to ON and set target temperature
        """

        hotwater = entity.component

        touch_system = await self._remove_quick_mode_or_holiday(entity)

        current_mode = self.system.get_active_mode_hot_water(hotwater).current

        if current_mode == OperatingModes.OFF or touch_system:
            await self._manager.set_hot_water_operating_mode(
                hotwater.id, OperatingModes.ON
            )
        await self._manager.set_hot_water_setpoint_temperature(hotwater.id, target_temp)

        self.system.hot_water = hotwater
        await self._refresh(touch_system, entity)

    async def set_room_target_temperature(self, entity, target_temp):
        """Set target temperature for a room.

        * If there is a quick mode that impact room running on or holiday mode,
        remove it.

        * If the room is in MANUAL mode, simply modify the target temperature.

        * if the room is not in MANUAL mode, create à quick veto.
        """

        touch_system = await self._remove_quick_mode_or_holiday(entity)

        room = entity.component
        current_mode = self.system.get_active_mode_room(room).current

        if current_mode == OperatingModes.MANUAL:
            await self._manager.set_room_setpoint_temperature(room.id, target_temp)
            room.target_temperature = target_temp
        else:
            if current_mode == OperatingModes.QUICK_VETO:
                await self._manager.remove_room_quick_veto(room.id)

            qveto = QuickVeto(DEFAULT_QUICK_VETO_DURATION, target_temp)
            await self._manager.set_room_quick_veto(room.id, qveto)
            room.quick_veto = qveto
        self.system.set_room(room.id, room)

        await self._refresh(touch_system, entity)

    async def set_zone_target_temperature(self, entity, target_temp):
        """Set target temperature for a zone.

        * If there is a quick mode related to zone running or holiday mode,
        remove it.

        * If quick veto running on, remove it and create a new one with the
            new target temp

        * If any other mode, create a quick veto
        """

        touch_system = await self._remove_quick_mode_or_holiday(entity)
        zone = entity.component
        current_mode = self.system.get_active_mode_zone(zone).current

        if current_mode == OperatingModes.QUICK_VETO:
            await self._manager.remove_zone_quick_veto(zone.id)

        veto = QuickVeto(None, target_temp)
        await self._manager.set_zone_quick_veto(zone.id, veto)
        zone.quick_veto = veto

        self.system.set_zone(zone.id, zone)
        await self._refresh(touch_system, entity)

    async def set_hot_water_operating_mode(self, entity, mode):
        """Set hot water operation mode.

        If there is a quick mode that impact hot warter running on or holiday
        mode, remove it.
        """
        hotwater = entity.component
        touch_system = await self._remove_quick_mode_or_holiday(entity)

        await self._manager.set_hot_water_operating_mode(hotwater.id, mode)
        hotwater.operating_mode = mode

        self.system.dhw.hotwater = hotwater
        await self._refresh(touch_system, entity)

    async def set_room_operating_mode(self, entity, room, mode):
        """Set room operation mode.

        If there is a quick mode that impact room running on or holiday mode,
        remove it.
        """
        touch_system = await self._remove_quick_mode_or_holiday(entity)
        if room.quick_veto is not None:
            await self._manager.remove_room_quick_veto(room.id)
            room.quick_veto = None

        await self._manager.set_room_operating_mode(room.id, mode)
        room.operating_mode = mode

        self.system.set_room(room.id, room)
        await self._refresh(touch_system, entity)

    async def set_zone_operating_mode(self, entity, mode):
        """Set zone operation mode.

        If there is a quick mode that impact zone running on or holiday mode,
        remove it.
        """
        touch_system = await self._remove_quick_mode_or_holiday(entity)
        zone = entity.component

        if zone.quick_veto is not None:
            await self._manager.remove_zone_quick_veto(zone.id)
            zone.quick_veto = None

        await self._manager.set_zone_operating_mode(zone.id, mode)
        zone.heating.operating_mode = mode

        self.system.set_zone(zone.id, zone)
        await self._refresh(touch_system, entity)

    async def remove_quick_mode(self, entity=None):
        """Remove quick mode.

        If entity is not None, only remove if the quick mode applies to the
        given entity.
        """
        if await self._remove_quick_mode_no_refresh(entity):
            await self._refresh_entities()

    async def remove_holiday_mode(self):
        """Remove holiday mode."""
        if await self._remove_holiday_mode_no_refresh():
            await self._refresh_entities()

    async def set_holiday_mode(self, start_date, end_date, temperature):
        """Set holiday mode."""
        await self._manager.set_holiday_mode(start_date, end_date, temperature)
        await self._refresh_entities()

    async def set_quick_mode(self, mode):
        """Set quick mode (remove evious one)."""
        await self._remove_quick_mode_no_refresh()
        await self._manager.set_quick_mode(QuickModes.get(mode))
        await self._refresh_entities()

    async def set_quick_veto(self, entity, temperature, duration=None):
        """Set quick veto for the given entity."""
        comp = self.find_component(entity.component)

        q_duration = duration if duration else DEFAULT_QUICK_VETO_DURATION
        qveto = QuickVeto(q_duration, temperature)

        if isinstance(comp, Zone):
            if comp.quick_veto:
                await self._manager.remove_zone_quick_veto(comp.id)
            await self._manager.set_zone_quick_veto(comp.id, qveto)
        else:
            if comp.quick_veto:
                await self._manager.remove_room_quick_veto(comp.id)
            await self._manager.set_room_quick_veto(comp.id, qveto)
        comp.quick_veto = qveto
        await self._refresh(False, entity)

    async def remove_quick_veto(self, entity):
        """Remove quick veto for the given entity."""
        comp = self.find_component(entity.component)

        if comp and comp.quick_veto:
            if isinstance(comp, Zone):
                await self._manager.remove_zone_quick_veto(comp.id)
            else:
                await self._manager.remove_room_quick_veto(comp.id)
            comp.quick_veto = None
            await self._refresh(False, entity)

    def get_entity(self, entity_id):
        """Get entity owned by this component."""
        for entity in self._hass.data[DOMAIN].entities:
            if entity.entity_id == entity_id:
                return entity
        return None

    async def _remove_quick_mode_no_refresh(self, entity=None):
        removed = False

        if self.system.quick_mode is not None:
            qmode = self.system.quick_mode

            if entity:
                if qmode.is_for(entity.component):
                    await self._hard_remove_quick_mode()
                    removed = True
            else:
                await self._hard_remove_quick_mode()
                removed = True
        return removed

    async def _hard_remove_quick_mode(self):
        await self._manager.remove_quick_mode()
        self.system.quick_mode = None

    async def _remove_holiday_mode_no_refresh(self):
        removed = False

        if self.system.holiday is not None and self.system.holiday.is_applied:
            removed = True
            await self._manager.remove_holiday_mode()
            self.system.holiday = HolidayMode(False)
        return removed

    async def _remove_quick_mode_or_holiday(self, entity):
        return await self._remove_holiday_mode_no_refresh() | await self._remove_quick_mode_no_refresh(
            entity
        )

    async def _refresh_entities(self):
        """Fetch vaillant data and force refresh of all listening entities."""
        await self.update_system(no_throttle=True)
        for entity in self._hass.data[DOMAIN].entities:
            if entity.listening:
                entity.async_schedule_update_ha_state(True)

    async def _refresh(self, touch_system, entity):
        if touch_system:
            await self._refresh_entities()
        else:
            entity.async_schedule_update_ha_state(True)


class DomainData:
    """Data for the integration."""

    def __init__(self, api: ApiHub, entry: ConfigEntry) -> None:
        """Init."""
        self.api = api
        self.entry = entry
        self.entities = []
