"""Support for the Netatmo climate schedule selector."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_URL_ENERGY,
    DATA_SCHEDULES,
    DOMAIN,
    EVENT_TYPE_SCHEDULE,
    MANUFACTURER,
    NETATMO_CREATE_SELECT,
)
from .data_handler import HOME, SIGNAL_NAME, NetatmoHome
from .entity import NetatmoBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
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

        self._attr_unique_id = f"{self.home.entity_id}-schedule-select"

        self._attr_current_option = getattr(self.home.get_selected_schedule(), "name")
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

    @callback
    def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        data = event["data"]

        if self.home.entity_id != data["home_id"]:
            return

        if data["event_type"] == EVENT_TYPE_SCHEDULE and "schedule_id" in data:
            self._attr_current_option = getattr(
                self.hass.data[DOMAIN][DATA_SCHEDULES][self.home.entity_id].get(
                    data["schedule_id"]
                ),
                "name",
            )
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        for sid, schedule in self.hass.data[DOMAIN][DATA_SCHEDULES][
            self.home.entity_id
        ].items():
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
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._attr_current_option = getattr(self.home.get_selected_schedule(), "name")
        self.hass.data[DOMAIN][DATA_SCHEDULES][self.home.entity_id] = (
            self.home.schedules
        )
        self._attr_options = [
            schedule.name for schedule in self.home.schedules.values() if schedule.name
        ]
