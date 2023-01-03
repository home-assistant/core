"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import logging

from pyrainbird import AvailableStations
from pyrainbird.async_client import AsyncRainbirdController, RainbirdApiException
from pyrainbird.data import States
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import ATTR_ENTITY_ID, CONF_FRIENDLY_NAME, CONF_TRIGGER_TIME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ZONES, DOMAIN, RAINBIRD_CONTROLLER
from .coordinator import RainbirdUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ATTR_DURATION = "duration"

SERVICE_START_IRRIGATION = "start_irrigation"
SERVICE_SET_RAIN_DELAY = "set_rain_delay"

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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Rain Bird switches over a Rain Bird controller."""

    if discovery_info is None:
        return

    controller: AsyncRainbirdController = discovery_info[RAINBIRD_CONTROLLER]
    try:
        available_stations: AvailableStations = (
            await controller.get_available_stations()
        )
    except RainbirdApiException as err:
        raise PlatformNotReady(f"Failed to get stations: {str(err)}") from err
    if not (available_stations and available_stations.stations):
        return
    coordinator = RainbirdUpdateCoordinator(hass, controller.get_zone_states)
    devices = []
    for zone in range(1, available_stations.stations.count + 1):
        if available_stations.stations.active(zone):
            zone_config = discovery_info.get(CONF_ZONES, {}).get(zone, {})
            time = zone_config.get(CONF_TRIGGER_TIME, discovery_info[CONF_TRIGGER_TIME])
            name = zone_config.get(CONF_FRIENDLY_NAME)
            devices.append(
                RainBirdSwitch(
                    coordinator,
                    controller,
                    zone,
                    time,
                    name if name else f"Sprinkler {zone}",
                )
            )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        raise PlatformNotReady(f"Failed to load zone state: {str(err)}") from err

    async_add_entities(devices)

    async def start_irrigation(service: ServiceCall) -> None:
        entity_id = service.data[ATTR_ENTITY_ID]
        duration = service.data[ATTR_DURATION]

        for device in devices:
            if device.entity_id == entity_id:
                await device.async_turn_on(duration=duration)

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_IRRIGATION,
        start_irrigation,
        schema=SERVICE_SCHEMA_IRRIGATION,
    )

    async def set_rain_delay(service: ServiceCall) -> None:
        duration = service.data[ATTR_DURATION]

        await controller.set_rain_delay(duration)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_RAIN_DELAY,
        set_rain_delay,
        schema=SERVICE_SCHEMA_RAIN_DELAY,
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
        time: int,
        name: str,
    ) -> None:
        """Initialize a Rain Bird Switch Device."""
        super().__init__(coordinator)
        self._rainbird = rainbird
        self._zone = zone
        self._name = name
        self._state = None
        self._duration = time
        self._attributes = {ATTR_DURATION: self._duration, "zone": self._zone}

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
            int(kwargs[ATTR_DURATION] if ATTR_DURATION in kwargs else self._duration),
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
