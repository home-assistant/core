"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import logging

from pyrainbird import AvailableStations
from pyrainbird.async_client import AsyncRainbirdController, RainbirdApiException
from pyrainbird.data import States
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DURATION,
    DEFAULT_TRIGGER_TIME_MINUTES,
    DEVICE_INFO,
    DOMAIN,
    RAINBIRD_CONTROLLER,
    SERIAL_NUMBER,
)
from .coordinator import RainbirdUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_START_IRRIGATION = "start_irrigation"

SERVICE_SCHEMA_IRRIGATION = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_DURATION): cv.positive_float,
    }
)

SERVICE_SCHEMA_RAIN_DELAY = vol.Schema(
    {
        vol.Required(ATTR_DURATION): cv.positive_float,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird irrigation switches."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    controller: AsyncRainbirdController = data[RAINBIRD_CONTROLLER]
    try:
        available_stations: AvailableStations = (
            await controller.get_available_stations()
        )
    except RainbirdApiException as err:
        raise PlatformNotReady(f"Failed to get stations: {str(err)}") from err
    if not (available_stations and available_stations.stations):
        return

    coordinator = RainbirdUpdateCoordinator(
        hass, "Zone States", controller.get_zone_states
    )
    await coordinator.async_config_entry_first_refresh()

    devices = []
    for zone in range(1, available_stations.stations.count + 1):
        if not available_stations.stations.active(zone):
            continue
        devices.append(
            RainBirdSwitch(
                coordinator,
                controller,
                zone,
                config_entry.options.get(ATTR_DURATION, DEFAULT_TRIGGER_TIME_MINUTES),
                data[SERIAL_NUMBER],
                data[DEVICE_INFO],
            )
        )

    async_add_devices(devices)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_START_IRRIGATION,
        SERVICE_SCHEMA_IRRIGATION,
        "async_turn_on",
    )


class RainBirdSwitch(
    CoordinatorEntity[RainbirdUpdateCoordinator[States]], SwitchEntity
):
    """Representation of a Rain Bird switch."""

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator[States],
        rainbird: AsyncRainbirdController,
        zone: int,
        duration_minutes: int,
        serial_number: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize a Rain Bird Switch Device."""
        super().__init__(coordinator)
        self._rainbird = rainbird
        self._zone = zone
        self._name = f"Sprinkler {zone}"
        self._state = None
        self._duration_minutes = duration_minutes
        self._attributes = {"zone": self._zone}
        self._attr_unique_id = f"{serial_number}-{zone}"
        self._attr_device_info = device_info

    @property
    def extra_state_attributes(self):
        """Return state attributes."""
        return self._attributes

    @property
    def name(self):
        """Get the name of the switch."""
        return self._name

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._rainbird.irrigate_zone(
            int(self._zone),
            int(kwargs.get(ATTR_DURATION, self._duration_minutes)),
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._rainbird.stop_irrigation()
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.coordinator.data.active(self._zone)
