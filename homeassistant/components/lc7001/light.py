"""Platform for light integration."""

from __future__ import annotations

import logging
import math
from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .common import LcConfigEntry
from .engine.engine import ConnectionState, Engine
from .engine.zone import SetZoneProperties, ZoneDeviceType, ZonePropertyList

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


def brightnessToHA(brightness: int) -> int:
    """Convert brightness from LC7001 to Home Assistant."""
    return math.floor(brightness * 255 / 100)


def brightnessToLC(brightness: int) -> int:
    """Convert brightness from Home Assistant to LC7001."""
    return math.floor(brightness * 100 / 255)


# Validation of the user's configuration
LIGHT_PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default="LCM1.local"): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config: LcConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the LC7001 platform."""

    engine: Engine = config.runtime_data

    @engine.on("StateChanged")
    def OnStateChanged(
        newState: ConnectionState, previousState: ConnectionState
    ) -> None:
        _LOGGER.debug("State changed from %s to %s", previousState.name, newState.name)

    # Initialize the representations in Home Assistant
    async_add_entities(
        Switch(engine=engine, ZID=ZID, properties=properties)
        for ZID, properties in engine.zones.items()
    )


class Switch(LightEntity):
    """Representation of a LC7001 Switch."""

    _attr_has_entity_name = True

    def __init__(self, engine: Engine, ZID: int, properties: ZonePropertyList) -> None:
        """Initialize."""
        self.engine = engine
        self.ZID = ZID
        self.properties = properties
        self.is_dimmer = self.properties.DeviceType == ZoneDeviceType.Dimmer.name

        self._attr_unique_id = f"{engine.systemInfo.MACAddress}-{ZID}"
        self._attr_name = self.properties.Name
        self._attr_is_on = self.properties.Power is True

        if self.is_dimmer:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            if properties.PowerLevel:
                self._attr_brightness = brightnessToHA(properties.PowerLevel)
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF

        engine.on("ZoneChanged", self.OnZoneChanged)

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        self.properties.Power = True
        self._attr_is_on = True

        # Don't see the power level unless:
        #   1. This is a dimmer
        #   2. There is an ATTR_BRIGHTNESS attribute
        PowerLevel: int | None = None
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if self.is_dimmer and brightness:
            self._attr_brightness = brightness
            PowerLevel = brightnessToLC(brightness)
            self.properties.PowerLevel = PowerLevel

        self.engine.sendPacket(
            SetZoneProperties(
                ZID=self.ZID,
                PropertyList=ZonePropertyList(Power=True, PowerLevel=PowerLevel),
            )
        )

        _LOGGER.debug("Turning ON %s (%s)", self.ZID, self.properties.Name)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self.properties.Power = False
        self._attr_is_on = False

        self.engine.sendPacket(
            SetZoneProperties(ZID=self.ZID, PropertyList=ZonePropertyList(Power=False))
        )

        _LOGGER.debug("Turning OFF %s (%s)", self.ZID, self.properties.Name)

    def update(self) -> None:
        """Fetch new state data for this light."""
        self._attr_name = self.properties.Name
        self._attr_is_on = self.properties.Power is True

        if self.is_dimmer and self.properties.PowerLevel:
            self._attr_brightness = brightnessToHA(self.properties.PowerLevel)

        _LOGGER.debug("Updating %s (%s)", self.ZID, self.properties.Name)

    def OnZoneChanged(
        self, ZID: int, changes: ZonePropertyList, **kwargs: dict[str, Any]
    ) -> None:
        """Invoke when the engine indicates a change on the switch."""
        if ZID != self.ZID:
            return

        _LOGGER.debug(
            "Applying changes to %s (%s): %s",
            self.ZID,
            self.properties.Name,
            vars(changes),
        )

        if changes.Name:
            self.properties.Name = changes.Name
            self._attr_name = changes.Name

        if changes.Power is not None:
            self.properties.Power = changes.Power
            self._attr_is_on = changes.Power

        if self.is_dimmer and changes.PowerLevel is not None:
            self.properties.PowerLevel = changes.PowerLevel
            self._attr_brightness = brightnessToHA(changes.PowerLevel)

        self.schedule_update_ha_state()
