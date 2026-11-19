"""Support for Honeywell Lyric switch platform."""

import logging
from typing import Any, override

from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    LYRIC_EXCEPTIONS,
    LYRIC_HVAC_MODE_EMERGENCY_HEAT,
    LYRIC_HVAC_MODE_HEAT,
)
from .coordinator import LyricConfigEntry, LyricDataUpdateCoordinator
from .entity import LyricDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LyricConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Honeywell Lyric switch entities based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        LyricEmergencyHeatSwitch(coordinator, location, device)
        for location in coordinator.data.locations
        for device in location.devices
        if LYRIC_HVAC_MODE_EMERGENCY_HEAT in device.allowed_modes
    )


class LyricEmergencyHeatSwitch(LyricDeviceEntity, SwitchEntity):
    """Switch entity for Honeywell Lyric thermostat emergency heat."""

    _attr_translation_key = "emergency_heat"

    def __init__(
        self,
        coordinator: LyricDataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
    ) -> None:
        """Initialize the emergency heat switch entity."""
        super().__init__(
            coordinator,
            location,
            device,
            f"{device.mac_id}_emergency_heat",
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if emergency heat is on."""
        return self.device.changeable_values.mode == LYRIC_HVAC_MODE_EMERGENCY_HEAT

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn emergency heat on."""
        await self._async_set_mode(LYRIC_HVAC_MODE_EMERGENCY_HEAT)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn emergency heat off, returning the thermostat to heat."""
        if self.is_on:
            await self._async_set_mode(LYRIC_HVAC_MODE_HEAT)

    async def _async_set_mode(self, mode: str) -> None:
        """Set the thermostat mode, then refresh the coordinator."""
        _LOGGER.debug("HVAC mode passed to lyric: %s", mode)
        try:
            await self._update_thermostat(self.location, self.device, mode=mode)
        except LYRIC_EXCEPTIONS as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_set_emergency_heat",
            ) from err
        finally:
            await self.coordinator.async_refresh()
