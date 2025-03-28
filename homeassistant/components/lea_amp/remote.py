"""Remote control support for LEA."""

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_HOLD_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LEAAMPApiCoordinator, LEAAMPConfigEntry
from .zone import LeaZone

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
COMMAND_TO_ATTRIBUTE = {
    "wakeup": ("power", "turn_on"),
    "suspend": ("power", "turn_off"),
    "turn_on": ("power", "turn_on"),
    "turn_off": ("power", "turn_off"),
    "volume_up": ("audio", "volume_up"),
    "volume_down": ("audio", "volume_down"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LEAAMPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Lea Zone setup."""

    coordinator = config_entry.runtime_data

    def discovery_callback(zone: LeaZone, is_new: bool) -> bool:
        if is_new:
            async_add_entities([LeaRemote(coordinator, zone)])
        return True

    async_add_entities(LeaRemote(coordinator, zone) for zone in coordinator.zones)

    await coordinator.set_discovery_callback(discovery_callback)


class LeaRemote(CoordinatorEntity[LEAAMPApiCoordinator], RemoteEntity):
    """Remote that sends commands to LeaZone."""

    _attr_translation_key = "lea_zone"
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = RemoteEntityFeature.ACTIVITY

    def __init__(
        self,
        coordinator: LEAAMPApiCoordinator,
        zone: LeaZone,
    ) -> None:
        """Lea Zone constructor."""

        super().__init__(coordinator)
        self._zone = zone
        zone.set_update_callback(self._update_callback)
        self._attr_unique_id = str(zone.zone_id)

        self._attr_zone_info = DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, str(zone.zone_id))
            },
            name=zone.zone_name,
            manufacturer=DOMAIN,
            model_id=zone.model,
            serial_number=str(zone.zone_id),
        )

    @property
    def is_on(self) -> bool:
        """Return true if zone is on."""
        return self._zone.power is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the Zone on."""
        _LOGGER.log(logging.INFO, "async_turn_on")
        _LOGGER.log(logging.INFO, "zone id: %s", str(self._zone.zone_id))
        _LOGGER.log(logging.INFO, "is on: %s", str(self.is_on))
        if not self.is_on:
            await self.coordinator.turn_on(self._zone)
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the Zone off."""
        _LOGGER.log(logging.INFO, "async_turn_off")
        _LOGGER.log(logging.INFO, "zone id: %s", str(self._zone.zone_id))
        _LOGGER.log(logging.INFO, "is on: %s", str(self.is_on))
        if self.is_on:
            await self.coordinator.turn_off(self._zone)
            self.async_write_ha_state()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to one zone."""
        num_repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        delay_secs = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        hold_secs = kwargs.get(ATTR_HOLD_SECS, DEFAULT_HOLD_SECS)

        for _ in range(num_repeats):
            for single_command in command:
                if hold_secs:
                    await self.coordinator.send_key_command(self._zone, single_command)
                    await asyncio.sleep(hold_secs)
                    await self.coordinator.send_key_command(self._zone, single_command)
                else:
                    await self.coordinator.send_key_command(self._zone, single_command)
                await asyncio.sleep(delay_secs)

    @callback
    def _update_callback(self, zone: LeaZone) -> None:
        self.async_write_ha_state()
