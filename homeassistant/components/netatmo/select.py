"""Support for the Netatmo climate schedule selector."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_URL_ENERGY,
    DATA_SCHEDULES,
    DOMAIN,
    EVENT_TYPE_SCHEDULE,
    NETATMO_CREATE_SELECT,
)
from .data_handler import HOME, SIGNAL_NAME, NetatmoHome
from .netatmo_entity_base import NetatmoBase

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


class NetatmoScheduleSelect(NetatmoBase, SelectEntity):
    """Representation a Netatmo thermostat schedule selector."""

    def __init__(
        self,
        netatmo_home: NetatmoHome,
    ) -> None:
        """Initialize the select entity."""
        SelectEntity.__init__(self)
        super().__init__(netatmo_home.data_handler)

        self._home = netatmo_home.home
        self._home_id = self._home.entity_id

        self._signal_name = netatmo_home.signal_name
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self._home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

        self._device_name = self._home.name
        self._attr_name = f"{self._device_name}"

        self._model: str = "NATherm1"
        self._config_url = CONF_URL_ENERGY

        self._attr_unique_id = f"{self._home_id}-schedule-select"

        self._attr_current_option = getattr(self._home.get_selected_schedule(), "name")
        self._attr_options = [
            schedule.name for schedule in self._home.schedules.values()
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

        if self._home_id != data["home_id"]:
            return

        if data["event_type"] == EVENT_TYPE_SCHEDULE and "schedule_id" in data:
            self._attr_current_option = getattr(
                self.hass.data[DOMAIN][DATA_SCHEDULES][self._home_id].get(
                    data["schedule_id"]
                ),
                "name",
            )
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        for sid, schedule in self.hass.data[DOMAIN][DATA_SCHEDULES][
            self._home_id
        ].items():
            if schedule.name != option:
                continue
            _LOGGER.debug(
                "Setting %s schedule to %s (%s)",
                self._home_id,
                option,
                sid,
            )
            await self._home.async_switch_schedule(schedule_id=sid)
            break

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._attr_current_option = getattr(self._home.get_selected_schedule(), "name")
        self.hass.data[DOMAIN][DATA_SCHEDULES][self._home_id] = self._home.schedules
        self._attr_options = [
            schedule.name for schedule in self._home.schedules.values()
        ]
