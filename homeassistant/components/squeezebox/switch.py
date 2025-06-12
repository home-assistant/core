"""Switch entity representing a Squeezebox alarm."""

import datetime
import logging
from typing import Any, cast

from pysqueezebox.player import Alarm

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change

from .const import ATTR_ALARM_ID, DOMAIN, SIGNAL_PLAYER_DISCOVERED
from .coordinator import SqueezeBoxPlayerUpdateCoordinator
from .entity import SqueezeboxEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Squeezebox alarm switch."""

    async def _player_discovered(
        coordinator: SqueezeBoxPlayerUpdateCoordinator,
    ) -> None:
        def _async_listener() -> None:
            """Handle alarm creation and deletion after coordinator data update."""
            new_alarms: set[str] = set()
            received_alarms: set[str] = set()

            if coordinator.data["alarms"] and coordinator.available:
                received_alarms = set(coordinator.data["alarms"])
                new_alarms = received_alarms - coordinator.known_alarms
            removed_alarms = coordinator.known_alarms - received_alarms

            if new_alarms:
                for new_alarm in new_alarms:
                    coordinator.known_alarms.add(new_alarm)
                    _LOGGER.debug(
                        "Setting up alarm entity for alarm %s on player %s",
                        new_alarm,
                        coordinator.player,
                    )
                    async_add_entities([SqueezeBoxAlarmEntity(coordinator, new_alarm)])

            if removed_alarms and coordinator.available:
                for removed_alarm in removed_alarms:
                    _uid = f"{coordinator.player_uuid}_alarm_{removed_alarm}"
                    _LOGGER.debug(
                        "Alarm %s with unique_id %s needs to be deleted",
                        removed_alarm,
                        _uid,
                    )

                    entity_registry = er.async_get(hass)
                    _entity_id = entity_registry.async_get_entity_id(
                        Platform.SWITCH,
                        DOMAIN,
                        _uid,
                    )
                    if _entity_id:
                        entity_registry.async_remove(_entity_id)
                        coordinator.known_alarms.remove(removed_alarm)

        _LOGGER.debug(
            "Setting up alarm enabled entity for player %s", coordinator.player
        )
        # Add listener first for future coordinator refresh
        coordinator.async_add_listener(_async_listener)

        # If coordinator already has alarm data from the initial refresh,
        # call the listener immediately to process existing alarms and create alarm entities.
        if coordinator.data["alarms"]:
            _LOGGER.debug(
                "Coordinator has alarm data, calling _async_listener immediately for player %s",
                coordinator.player,
            )
            _async_listener()
        async_add_entities([SqueezeBoxAlarmsEnabledEntity(coordinator)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_PLAYER_DISCOVERED, _player_discovered)
    )


class SqueezeBoxAlarmEntity(SqueezeboxEntity, SwitchEntity):
    """Representation of a Squeezebox alarm switch."""

    _attr_translation_key = "alarm"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: SqueezeBoxPlayerUpdateCoordinator, alarm_id: str
    ) -> None:
        """Initialize the Squeezebox alarm switch."""
        super().__init__(coordinator)
        self._alarm_id = alarm_id
        self._attr_translation_placeholders = {"alarm_id": self._alarm_id}
        self._attr_unique_id: str = (
            f"{format_mac(self._player.player_id)}_alarm_{self._alarm_id}"
        )

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
        return self.coordinator.data["alarms"][self._alarm_id]

    @property
    def available(self) -> bool:
        """Return whether the alarm is available."""
        return super().available and self._alarm_id in self.coordinator.data["alarms"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes of Squeezebox alarm switch."""
        return {ATTR_ALARM_ID: str(self._alarm_id)}

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return cast(bool, self.alarm["enabled"])

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.coordinator.player.async_update_alarm(self._alarm_id, enabled=False)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.coordinator.player.async_update_alarm(self._alarm_id, enabled=True)
        await self.coordinator.async_request_refresh()


class SqueezeBoxAlarmsEnabledEntity(SqueezeboxEntity, SwitchEntity):
    """Representation of a Squeezebox players alarms enabled master switch."""

    _attr_translation_key = "alarms_enabled"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: SqueezeBoxPlayerUpdateCoordinator) -> None:
        """Initialize the Squeezebox alarm switch."""
        super().__init__(coordinator)
        self._attr_unique_id: str = (
            f"{format_mac(self._player.player_id)}_alarms_enabled"
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return cast(bool, self.coordinator.player.alarms_enabled)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.coordinator.player.async_set_alarms_enabled(False)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.coordinator.player.async_set_alarms_enabled(True)
        await self.coordinator.async_request_refresh()
