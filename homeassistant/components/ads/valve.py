"""Support for ADS valves."""

from __future__ import annotations

import asyncio

import pyads
import voluptuous as vol

from homeassistant.components.valve import (
    DEVICE_CLASSES_SCHEMA as VALVE_DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as VALVE_PLATFORM_SCHEMA,
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .. import ads
from . import CONF_ADS_VAR, AdsEntity

DEFAULT_NAME = "ADS valve"

PLATFORM_SCHEMA = VALVE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADS_VAR): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): VALVE_DEVICE_CLASSES_SCHEMA,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an ADS valve device."""
    ads_hub: ads.AdsHub = hass.data[ads.DATA_ADS]
    ads_var = config[CONF_ADS_VAR]
    name = config[CONF_NAME]
    device_class = config.get(CONF_DEVICE_CLASS)

    entity = AdsValve(ads_hub, ads_var, name, device_class)

    add_entities([entity])


class AdsValve(AdsEntity, ValveEntity):
    """Representation of an ADS valve entity."""

    def __init__(
        self,
        ads_hub: ads.AdsHub,
        ads_var: str,
        name: str,
        device_class: ValveDeviceClass | None,
    ) -> None:
        """Initialize AdsValve entity."""
        super().__init__(ads_hub, name, ads_var)
        self._attr_device_class = device_class
        self._attr_supported_features = (
            ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
        )
        self._attr_reports_position = False
        self._attr_is_closed = True

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, pyads.PLCTYPE_BOOL)

    @property
    def supported_features(self) -> ValveEntityFeature:
        """Return the list of supported features."""
        return ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    @property
    def is_open(self) -> bool | None:
        """Return True if the valve is open."""
        return not self._attr_is_closed

    @property
    def is_closed(self) -> bool | None:
        """Return True if the valve is closed."""
        return self._attr_is_closed

    async def async_open_valve(self, **kwargs) -> None:
        """Open the valve."""
        if self._ads_hub is None:
            raise RuntimeError("ADS Hub is not initialized.")

        # Run synchronous write_by_name in executor if needed
        await asyncio.get_event_loop().run_in_executor(
            None, self._ads_hub.write_by_name, self._ads_var, True, pyads.PLCTYPE_BOOL
        )

    async def async_close_valve(self, **kwargs) -> None:
        """Close the valve."""
        if self._ads_hub is None:
            raise RuntimeError("ADS Hub is not initialized.")

        # Run synchronous write_by_name in executor if needed
        await asyncio.get_event_loop().run_in_executor(
            None, self._ads_hub.write_by_name, self._ads_var, False, pyads.PLCTYPE_BOOL
        )
