"""Support for GPSD."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_ELEVATION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MODE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_CLIMB, ATTR_GPS_TIME, ATTR_SPEED
from .coordinator import GpsdCoordinator

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "GPS"
DEFAULT_PORT = 2947

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the GPSD component."""
    coordinator = GpsdCoordinator(hass, config)
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise PlatformNotReady

    add_entities(
        [
            GpsdSensor(
                hass,
                coordinator,
                config[CONF_NAME],
                config[CONF_HOST],
                config[CONF_PORT],
            )
        ]
    )


class GpsdSensor(CoordinatorEntity[GpsdCoordinator], SensorEntity):
    """Representation of a GPS receiver available via GPSD."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: GpsdCoordinator,
        name: str,
        host: str,
        port: int,
    ) -> None:
        """Initialize the GPSD sensor."""
        super().__init__(coordinator)

        self.hass = hass
        self._name = name
        self._host = host
        self._port = port

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def native_value(self) -> str | None:
        """Return the state of GPSD."""
        if self.coordinator.data["mode"] == 3:
            return "3D Fix"
        if self.coordinator.data["mode"] == 2:
            return "2D Fix"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the GPS."""
        return {
            ATTR_LATITUDE: self.coordinator.data["latitude"],
            ATTR_LONGITUDE: self.coordinator.data["longitude"],
            ATTR_ELEVATION: self.coordinator.data["elevation"],
            ATTR_GPS_TIME: self.coordinator.data["gps_time"],
            ATTR_SPEED: self.coordinator.data["speed"],
            ATTR_CLIMB: self.coordinator.data["climb"],
            ATTR_MODE: self.coordinator.data["mode"],
        }

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        mode = self.coordinator.data["mode"]

        if isinstance(mode, int) and mode >= 2:
            return "mdi:crosshairs-gps"
        return "mdi:crosshairs"
