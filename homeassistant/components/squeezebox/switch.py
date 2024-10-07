"""Switch entity representing a Squeezebox alarm."""

import datetime
import logging
from typing import Any

from pysqueezebox.player import Alarm
import voluptuous as vol

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    entity_platform,
    entity_registry as er,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ALARM_ID,
    ATTR_DAYS_OF_WEEK,
    ATTR_ENABLED,
    ATTR_REPEAT,
    ATTR_SCHEDULED_TODAY,
    ATTR_TIME,
    ATTR_URL,
    ATTR_VOLUME,
    SIGNAL_ALARM_DISCOVERED,
)
from .coordinator import SqueezeBoxPlayerUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_DELETE_ALARM = "delete_alarm"
SERVICE_UPDATE_ALARM = "update_alarm"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Squeezebox alarm switch."""

    # create a new alarm entity if it doesn't already exist
    async def _alarm_discovered(
        alarm: Alarm,
        coordinator: SqueezeBoxPlayerUpdateCoordinator,
    ) -> None:
        _LOGGER.debug(
            "Setting up alarm entity for alarm %s on player %s",
            alarm["id"],
            coordinator.player,
        )
        async_add_entities([SqueezeBoxAlarmEntity(alarm, coordinator)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_ALARM_DISCOVERED, _alarm_discovered)
    )

    # register services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_DELETE_ALARM,
        {},
        "async_delete_alarm",
    )
    platform.async_register_entity_service(
        SERVICE_UPDATE_ALARM,
        {
            vol.Optional(ATTR_TIME): cv.time,
            vol.Optional(ATTR_DAYS_OF_WEEK): cv.string,
            vol.Optional(ATTR_ENABLED): cv.boolean,
            vol.Optional(ATTR_REPEAT): cv.string,
            vol.Optional(ATTR_VOLUME): cv.positive_int,
            vol.Optional(ATTR_URL): cv.url,
        },
        "async_update_alarm",
    )


class SqueezeBoxAlarmEntity(
    CoordinatorEntity[SqueezeBoxPlayerUpdateCoordinator], SwitchEntity
):
    """Representation of a Squeezebox alarm switch."""

    _attr_icon = "mdi:alarm"

    def __init__(
        self, alarm: Alarm, coordinator: SqueezeBoxPlayerUpdateCoordinator
    ) -> None:
        """Initialize the Squeezebox alarm switch."""
        super().__init__(coordinator)
        self._alarm: Alarm | None = alarm
        self._attr_unique_id: str = f"{coordinator.player_uuid}-alarm-{alarm["id"]}"
        self.entity_id: str = ENTITY_ID_FORMAT.format(
            f"squeezebox_alarm_{self.alarm["id"]}"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if "alarms" not in self.coordinator.data:
            self._alarm = None
            return
        self._alarm = self.coordinator.data["alarms"].get(self.alarm["id"])
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Set up alarm switch when added to hass."""
        await super().async_added_to_hass()

        async def async_write_state_daily(now: datetime.datetime) -> None:
            """Update alarm state attributes each calendar day."""
            _LOGGER.debug("Updating state attributes for %s", self.name)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_time_change(
                self.hass, async_write_state_daily, hour=0, minute=0, second=0
            )
        )

    async def _async_handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.async_check_if_available():
            return
        self.async_write_ha_state()

    def async_check_if_available(self) -> bool:
        """Check if alarm exists and interpret meaning if not available."""
        if self.alarm:
            return True

        if not self.coordinator.available:
            # The player is not available, so the alarm is not available but probably still exists
            self._attr_available = False
            return False

        # The alarm is not available, but the player is, so the alarm has been deleted
        _LOGGER.debug("%s has been deleted", self.entity_id)

        entity_registry = er.async_get(self.hass)
        if entity_registry.async_get(self.entity_id):
            entity_registry.async_remove(self.entity_id)
            self.coordinator.known_alarms.remove(self.alarm["id"])

        return False

    @property
    def alarm(self) -> Alarm:
        """Return the alarm object."""
        return self._alarm

    @property
    def available(self) -> bool:
        """Return whether the alarm is available."""
        return self._attr_available and super().available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes of Squeezebox alarm switch."""
        return {
            ATTR_ALARM_ID: str(self.alarm["id"]),
            ATTR_TIME: str(self.alarm["time"]),
            ATTR_REPEAT: str(self.alarm["repeat"]),
            ATTR_DAYS_OF_WEEK: str(self.alarm["dow"]),
            ATTR_VOLUME: self.alarm["volume"] / 100,
            ATTR_URL: self.alarm["url"],
            ATTR_SCHEDULED_TODAY: self._is_today,
        }

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.alarm is not None and self.alarm["enabled"]

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return f"{self.coordinator.player.name} Alarm {self.alarm["id"]}"

    @property
    def _is_today(self) -> bool:
        """Return whether this alarm is scheduled for today."""
        daynum = int(datetime.datetime.today().strftime("%w"))
        return daynum in self.alarm["dow"]

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.coordinator.player.async_update_alarm(
            self.alarm["id"], enabled=False
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.coordinator.player.async_update_alarm(self.alarm["id"], enabled=True)
        await self.coordinator.async_request_refresh()

    async def async_update_alarm(self, **kwargs: Any) -> None:
        """Update the alarm."""
        try:
            alarm = self.alarm.copy()
            alarm.update(kwargs)
        except (TypeError, ValueError) as err:
            raise ServiceValidationError from err
        await self.coordinator.player.async_update_alarm(alarm.pop("id"), **alarm)
        await self.coordinator.async_request_refresh()

    async def async_delete_alarm(self) -> None:
        """Delete the alarm."""
        await self.coordinator.player.async_delete_alarm(self.alarm["id"])
        await self.coordinator.async_request_refresh()
