"""Support for the Netatmo climate schedule selector."""
from __future__ import annotations

import logging
from typing import cast

import pyatmo

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_HANDLER,
    DATA_SCHEDULES,
    DOMAIN,
    EVENT_TYPE_SCHEDULE,
    MANUFACTURER,
    SIGNAL_NAME,
)
from .data_handler import HOMEDATA_DATA_CLASS_NAME, NetatmoDataHandler
from .helper import get_all_home_ids, update_climate_schedules
from .netatmo_entity_base import NetatmoBase

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netatmo energy platform schedule selector."""
    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]

    await data_handler.register_data_class(
        HOMEDATA_DATA_CLASS_NAME, HOMEDATA_DATA_CLASS_NAME, None
    )
    home_data = data_handler.data.get(HOMEDATA_DATA_CLASS_NAME)

    if not home_data or home_data.raw_data == {}:
        raise PlatformNotReady

    hass.data[DOMAIN][DATA_SCHEDULES].update(
        update_climate_schedules(
            home_ids=get_all_home_ids(home_data),
            schedules=data_handler.data[HOMEDATA_DATA_CLASS_NAME].schedules,
        )
    )

    entities = [
        NetatmoScheduleSelect(
            data_handler,
            home_id,
            list(hass.data[DOMAIN][DATA_SCHEDULES][home_id].values()),
        )
        for home_id in hass.data[DOMAIN][DATA_SCHEDULES]
    ]

    _LOGGER.debug("Adding climate schedule select entities %s", entities)
    async_add_entities(entities, True)


class NetatmoScheduleSelect(NetatmoBase, SelectEntity):
    """Representation a Netatmo thermostat schedule selector."""

    def __init__(
        self, data_handler: NetatmoDataHandler, home_id: str, options: list
    ) -> None:
        """Initialize the select entity."""
        SelectEntity.__init__(self)
        super().__init__(data_handler)

        self._home_id = home_id

        self._data_classes.extend(
            [
                {
                    "name": HOMEDATA_DATA_CLASS_NAME,
                    SIGNAL_NAME: HOMEDATA_DATA_CLASS_NAME,
                },
            ]
        )

        self._device_name = self._data.homes[home_id]["name"]
        self._attr_name = f"{MANUFACTURER} {self._device_name}"

        self._model: str = "NATherm1"

        self._attr_unique_id = f"{self._home_id}-schedule-select"

        self._attr_current_option = self._data._get_selected_schedule(
            home_id=self._home_id
        ).get("name")
        self._attr_options = options

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        for event_type in (EVENT_TYPE_SCHEDULE,):
            self._listeners.append(
                async_dispatcher_connect(
                    self.hass,
                    f"signal-{DOMAIN}-webhook-{event_type}",
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
            self._attr_current_option = self.hass.data[DOMAIN][DATA_SCHEDULES][
                self._home_id
            ].get(data["schedule_id"])
            self.async_write_ha_state()

    @property
    def _data(self) -> pyatmo.AsyncHomeData:
        """Return data for this entity."""
        return cast(
            pyatmo.AsyncHomeData,
            self.data_handler.data[self._data_classes[0]["name"]],
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        for sid, name in self.hass.data[DOMAIN][DATA_SCHEDULES][self._home_id].items():
            if name != option:
                continue
            _LOGGER.debug(
                "Setting %s schedule to %s (%s)",
                self._home_id,
                option,
                sid,
            )
            await self._data.async_switch_home_schedule(
                home_id=self._home_id, schedule_id=sid
            )
            break

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._attr_current_option = (
            self._data._get_selected_schedule(  # pylint: disable=protected-access
                home_id=self._home_id
            ).get("name")
        )
        self.hass.data[DOMAIN][DATA_SCHEDULES][self._home_id] = {
            schedule_id: schedule_data.get("name")
            for schedule_id, schedule_data in (
                self._data.schedules[self._home_id].items()
            )
        }
        self._attr_options = list(
            self.hass.data[DOMAIN][DATA_SCHEDULES][self._home_id].values()
        )
