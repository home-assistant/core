"""Support for the Netatmo climate schedule selector."""

import logging
from typing import override

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_URL_ENERGY,
    DOMAIN,
    EVENT_TYPE_SCHEDULE,
    MANUFACTURER,
    NETATMO_CREATE_SELECT,
)
from .coordinator import HOME, SIGNAL_NAME, NetatmoConfigEntry, NetatmoHome
from .entity import NetatmoBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetatmoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Netatmo energy platform schedule selector."""

    @callback
    def _create_entity(netatmo_home: NetatmoHome) -> None:
        entity = NetatmoScheduleSelect(netatmo_home)
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
            ]
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.home.entity_id)},
            name=self.home.name,
            manufacturer=MANUFACTURER,
            model="Climate",
            configuration_url=CONF_URL_ENERGY,
        )

        self._attr_unique_id = f"{self.home.entity_id}-schedule-select"  # pylint: disable=home-assistant-entity-unique-id-redundant-platform

        schedule = self.home.get_selected_schedule()
        assert schedule
        self._attr_current_option = schedule.name
        self._attr_options = [
            schedule.name for schedule in self.home.schedules.values() if schedule.name
        ]

    @override
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

    @callback
    def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        data = event["data"]

        if self.home.entity_id != data["home_id"]:
            return

        if data["event_type"] == EVENT_TYPE_SCHEDULE and "schedule_id" in data:
            if schedule := self.data_handler.schedules[self.home.entity_id].get(
                data["schedule_id"]
            ):
                self._attr_current_option = schedule.name
                self.async_write_ha_state()

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        for sid, schedule in self.data_handler.schedules[self.home.entity_id].items():
            if schedule.name != option:
                continue
            _LOGGER.debug(
                "Setting %s schedule to %s (%s)",
                self.home.entity_id,
                option,
                sid,
            )
            await self.home.async_switch_schedule(schedule_id=sid)
            break

    @callback
    @override
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        schedule = self.home.get_selected_schedule()
        assert schedule
        self._attr_current_option = schedule.name
        self.data_handler.schedules[self.home.entity_id] = self.home.schedules
        self._attr_options = [
            schedule.name for schedule in self.home.schedules.values() if schedule.name
        ]
