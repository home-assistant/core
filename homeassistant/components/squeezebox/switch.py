"""Switch entity representing a Squeezebox alarm."""

import datetime
import logging
from typing import Any

from pysqueezebox.player import Alarm

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change

from .const import ATTR_ALARM_ID, SIGNAL_ALARM_DISCOVERED, SIGNAL_PLAYER_DISCOVERED
from .coordinator import SqueezeBoxPlayerUpdateCoordinator
from .entity import SqueezeboxEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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

    # create a new alarm enabled entity upon player discovery
    async def _player_discovered(
        coordinator: SqueezeBoxPlayerUpdateCoordinator,
    ) -> None:
        _LOGGER.debug(
            "Setting up alarm enabled entity for player %s", coordinator.player
        )
        async_add_entities([SqueezeBoxAlarmsEnabledEntity(coordinator)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_PLAYER_DISCOVERED, _player_discovered)
    )


class SqueezeBoxAlarmEntity(SqueezeboxEntity, SwitchEntity):
    """Representation of a Squeezebox alarm switch."""

    _attr_translation_key = "alarm"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, alarm: Alarm, coordinator: SqueezeBoxPlayerUpdateCoordinator
    ) -> None:
        """Initialize the Squeezebox alarm switch."""
        super().__init__(coordinator)
        self._alarm: Alarm | None = alarm
        self._attr_available = True
        self._attr_translation_placeholders = {"alarm_id": alarm["id"]}
        self._attr_unique_id: str = (
            f"{format_mac(self._player.player_id)}-alarm-{alarm['id']}"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            "alarms" not in self.coordinator.data
            or self.coordinator.data["alarms"].get(self.alarm["id"]) is None
        ):
            self._attr_available = False
            self.check_if_deleted()
        else:
            self._alarm = self.coordinator.data["alarms"].get(self.alarm["id"])
        self.async_write_ha_state()

    def check_if_deleted(self) -> None:
        """Check if alarm has been deleted from player."""
        if not self.coordinator.available:
            # The player is not available, so the alarm is not available but probably still exists
            return

        # The alarm is not available, but the player is, so the alarm has been deleted
        _LOGGER.debug("%s has been deleted", self.entity_id)

        entity_registry = er.async_get(self.hass)
        if entity_registry.async_get(self.entity_id):
            entity_registry.async_remove(self.entity_id)
            self.coordinator.known_alarms.remove(self.alarm["id"])

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
        return {ATTR_ALARM_ID: str(self.alarm["id"])}

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.alarm is not None and self.alarm["enabled"]

    @property
    def _is_today(self) -> bool:
        """Return whether this alarm is scheduled for today."""
        daynum = datetime.datetime.today().weekday()
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


class SqueezeBoxAlarmsEnabledEntity(SqueezeboxEntity, SwitchEntity):
    """Representation of a Squeezebox players alarms enabled master switch."""

    _attr_translation_key = "alarms_enabled"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: SqueezeBoxPlayerUpdateCoordinator) -> None:
        """Initialize the Squeezebox alarm switch."""
        super().__init__(coordinator)
        self._attr_available = True
        self._attr_unique_id: str = (
            f"{format_mac(self._player.player_id)}-alarms-enabled"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.coordinator.player.alarms_enabled is True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.coordinator.player.async_set_alarms_enabled(False)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.coordinator.player.async_set_alarms_enabled(True)
        await self.coordinator.async_request_refresh()
