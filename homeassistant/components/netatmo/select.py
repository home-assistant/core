"""Support for the Netatmo climate schedule selector."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_URL_ENERGY,
    DATA_SCHEDULES,
    DOMAIN,
    EVENT_TYPE_SCHEDULE,
    MANUFACTURER,
    NETATMO_CREATE_SELECT,
    SIGNAL_SCHEDULE_CHANGED,
)
from .data_handler import ACCOUNT, HOME, SIGNAL_NAME, NetatmoHome
from .entity import NetatmoBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Netatmo energy platform schedule selector."""

    @callback
    def _create_entity(netatmo_home: NetatmoHome) -> None:
        entity = NetatmoScheduleSelect(netatmo_home)
        _LOGGER.debug("Adding schedule select for home %s", netatmo_home.home.name)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_SELECT, _create_entity)
    )


class NetatmoScheduleSelect(NetatmoBaseEntity, SelectEntity):
    """Representation a Netatmo thermostat schedule selector."""

    _attr_name = None

    def __init__(self, netatmo_home: NetatmoHome) -> None:
        """Initialize the select entity."""
        super().__init__(netatmo_home.data_handler)

        self.home = netatmo_home.home

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: netatmo_home.signal_name,
                },
                {
                    "name": ACCOUNT,
                    SIGNAL_NAME: ACCOUNT,
                },
            ]
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.home.entity_id)},
            name=self.home.name,
            manufacturer=MANUFACTURER,
            model="Climate",
            configuration_url=CONF_URL_ENERGY,
        )

        self._attr_unique_id = f"{self.home.entity_id}-schedule-select"

        schedule = self.home.get_selected_schedule()
        self._attr_current_option = schedule.name if schedule else None
        self._attr_options = [
            schedule.name for schedule in self.home.schedules.values() if schedule.name
        ]

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"signal-{DOMAIN}-webhook-{EVENT_TYPE_SCHEDULE}",
                self.handle_event,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_SCHEDULE_CHANGED}-{self.home.entity_id}",
                self._handle_schedule_changed,
            )
        )

    @callback
    def _handle_schedule_changed(self, schedule_id: str) -> None:
        """Handle schedule change triggered by another entity."""
        schedule = self.hass.data[DOMAIN][DATA_SCHEDULES].get(
            self.home.entity_id, {}
        ).get(schedule_id)
        new_option = getattr(schedule, "name", None)
        if new_option == self._attr_current_option:
            return  # already up to date
        # update in-memory selection state
        for sid, sched in self.home.schedules.items():
            sched.selected = sid == schedule_id
        _LOGGER.debug(
            "Schedule changed for home %s (%s): %s -> %s [trigger: internal]",
            self.home.name,
            self.home.entity_id,
            self._attr_current_option,
            new_option,
        )
        self._attr_current_option = new_option
        self.async_write_ha_state()

    @callback
    def handle_event(self, event: dict) -> None:
        """Handle schedule change triggered by a Netatmo webhook event."""
        data = event["data"]

        if self.home.entity_id != data["home_id"]:
            return

        if data["event_type"] == EVENT_TYPE_SCHEDULE and "schedule_id" in data:
            new_schedule_id = data["schedule_id"]
            # look up the schedule object from the local cache by id
            schedule = self.hass.data[DOMAIN][DATA_SCHEDULES].get(
                self.home.entity_id, {}
            ).get(new_schedule_id)
            new_option = getattr(schedule, "name", None)
            if new_option != self._attr_current_option:
                _LOGGER.debug(
                    "Schedule changed for home %s (%s): %s -> %s [trigger: webhook]",
                    self.home.name,
                    self.home.entity_id,
                    self._attr_current_option,
                    new_option,
                )
            else:
                _LOGGER.debug(
                    "Schedule selection confirmed for home %s (%s): %s [trigger: webhook]",
                    self.home.name,
                    self.home.entity_id,
                    new_option,
                )
            # update in-memory selection state to prevent stale poll from reverting
            for sid, sched in self.home.schedules.items():
                sched.selected = sid == new_schedule_id
            self._attr_current_option = new_option
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Handle schedule change triggered by a user selection in the UI."""
        for sid, schedule in self.hass.data[DOMAIN][DATA_SCHEDULES].get(
            self.home.entity_id, {}
        ).items():
            if schedule.name != option:
                continue
            _LOGGER.debug(
                "Schedule changed for home %s (%s): %s -> %s [trigger: user]",
                self.home.name,
                self.home.entity_id,
                self._attr_current_option,
                option,
            )
            await self.home.async_switch_schedule(schedule_id=sid)
            # update in-memory selection state to prevent stale poll from reverting
            for s, sched in self.home.schedules.items():
                sched.selected = s == sid
            self._attr_current_option = option
            self.async_write_ha_state()
            # notify other entities of the schedule change
            async_dispatcher_send(
                self.hass,
                f"{SIGNAL_SCHEDULE_CHANGED}-{self.home.entity_id}",
                sid,
            )
            # trigger immediate homesdata refresh to confirm schedule selection
            self.data_handler.async_force_update(ACCOUNT)
            return

        _LOGGER.error(
            "%s is not a valid schedule for home %s",
            option,
            self.home.name,
        )

    @callback
    def async_update_callback(self) -> None:
        """Handle schedule change triggered by a Netatmo API poll."""
        # note that schedule.selected is populated from homesdata, not homestatus
        schedule = self.home.get_selected_schedule()
        if schedule is None:
            _LOGGER.debug("No selected schedule found for home %s", self.home.entity_id)
            self._attr_available = False
            return
        self._attr_available = True
        if schedule.name != self._attr_current_option:
            _LOGGER.debug(
                "Schedule changed for home %s (%s): %s -> %s [trigger: api poll]",
                self.home.name,
                self.home.entity_id,
                self._attr_current_option,
                schedule.name,
            )
            self._attr_current_option = schedule.name
        else:
            _LOGGER.debug(
                "Schedule selection confirmed for home %s (%s): %s [trigger: api poll]",
                self.home.name,
                self.home.entity_id,
                schedule.name,
            )
        # update local schedule cache and options list
        self.hass.data[DOMAIN][DATA_SCHEDULES][self.home.entity_id] = (
            self.home.schedules
        )
        self._attr_options = [
            schedule.name for schedule in self.home.schedules.values() if schedule.name
        ]
