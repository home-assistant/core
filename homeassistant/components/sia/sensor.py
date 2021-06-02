"""Module for SIA Sensors."""
from __future__ import annotations

from datetime import datetime as dt, timedelta
import logging
from typing import Any

from pysiaalarm import SIAEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, DEVICE_CLASS_TIMESTAMP
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_PING_INTERVAL,
    DOMAIN,
    SIA_EVENT,
    SIA_NAME_FORMAT_SENSOR,
    SIA_UNIQUE_ID_FORMAT_SENSOR,
)
from .utils import get_attr_from_sia_event

_LOGGER = logging.getLogger(__name__)

REGULAR_ICON = "mdi:clock-check"
LATE_ICON = "mdi:clock-alert"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sia_sensor from a config entry."""
    async_add_entities(
        SIASensor(entry, account_data) for account_data in entry.data[CONF_ACCOUNTS]
    )


class SIASensor(RestoreEntity):
    """Class for SIA Sensors."""

    def __init__(
        self,
        entry: ConfigEntry,
        account_data: dict[str, Any],
    ) -> None:
        """Create SIASensor object."""
        self._entry: ConfigEntry = entry
        self._account_data: dict[str, Any] = account_data

        self._port: int = self._entry.data[CONF_PORT]
        self._account: str = self._account_data[CONF_ACCOUNT]
        self._ping_interval: timedelta = timedelta(
            minutes=self._account_data[CONF_PING_INTERVAL]
        )

        self._state: dt = utcnow()
        self._cancel_icon_cb: CALLBACK_TYPE | None = None

        self._attr_extra_state_attributes: dict[str, Any] = {}
        self._attr_icon = REGULAR_ICON
        self._attr_unit_of_measurement = "ISO8601"
        self._attr_device_class = DEVICE_CLASS_TIMESTAMP
        self._attr_should_poll = False
        self._attr_name = SIA_NAME_FORMAT_SENSOR.format(self._port, self._account)
        self._attr_unique_id = SIA_UNIQUE_ID_FORMAT_SENSOR.format(
            self._entry.entry_id, self._account
        )

    async def async_added_to_hass(self) -> None:
        """Once the sensor is added, see if it was there before and pull in that state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state is not None:
            self._state = dt.fromisoformat(last_state.state)
        self._update_icon()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIA_EVENT.format(self._port, self._account),
                self.async_handle_event,
            )
        )
        self.async_on_remove(
            async_track_time_interval(self.hass, self._update_icon, self._ping_interval)
        )

    async def async_handle_event(self, sia_event: SIAEvent):
        """Listen to events for this port and account and update the state and attributes."""
        self._attr_extra_state_attributes.update(get_attr_from_sia_event(sia_event))
        if sia_event.code == "RP":
            self._state = utcnow()
        self._update_icon()

    @callback
    def _update_icon(self, *_) -> None:
        """Update the icon."""
        if self._state < utcnow() - self._ping_interval:
            self._attr_icon = LATE_ICON
        else:
            self._attr_icon = REGULAR_ICON
        self.async_write_ha_state()

    @property
    def state(self) -> StateType:
        """Return state."""
        return self._state.isoformat()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info."""
        assert self._attr_unique_id is not None
        assert self._attr_name is not None
        return {
            "name": self._attr_name,
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "via_device": (DOMAIN, f"{self._port}_{self._account}"),
        }
