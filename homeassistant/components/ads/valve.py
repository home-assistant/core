"""Support for ADS valve."""

from datetime import timedelta

import pyads
import voluptuous as vol

from homeassistant.components.valve import (
    PLATFORM_SCHEMA as VALVE_PLATFORM_SCHEMA,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .. import ads
from . import AdsEntity

SCAN_INTERVAL = timedelta(seconds=5)
DEFAULT_NAME = "ADS Valve"

CONF_ADS_VAR = "adsvar"

PLATFORM_SCHEMA = VALVE_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_VAR): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the valve platform for ADS."""
    ads_hub = hass.data.get(ads.DATA_ADS)
    ads_var = config.get(CONF_ADS_VAR)
    name = config[CONF_NAME]

    add_entities(
        [
            AdsValve(
                ads_hub,
                ads_var,
                name,
            )
        ]
    )


class AdsValve(AdsEntity, ValveEntity):
    """Representation of ADS valve entity."""

    def __init__(
        self,
        ads_hub,
        ads_var,
        name,
    ):
        """Initialize AdsValve entity."""
        super().__init__(ads_hub, name, ads_var)
        self._ads_var_state = ads_var
        self._name = name
        self._attr_is_closed = False
        self._attr_supported_features = (
            ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
        )
        self._attr_reports_position = False

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        if self._ads_var:
            await self.async_initialize_device(self._ads_var, pyads.PLCTYPE_BOOL)

        self.async_schedule_update_ha_state(True)

    @property
    def should_poll(self) -> bool:
        """Return True if the entity should be polled."""
        return True

    @property
    def name(self) -> str:
        """Return the name of the valve device."""
        return self._name

    @property
    def is_closed(self) -> bool | None:
        """Return True if the valve is open."""
        return self._attr_is_closed

    @property
    def supported_features(self) -> ValveEntityFeature:
        """Return the list of supported features."""
        return ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    async def async_open_valve(self) -> None:
        """Open the valve."""
        self._ads_hub.write_by_name(self._ads_var, True, pyads.PLCTYPE_BOOL)
        self._attr_is_closed = False
        self.async_schedule_update_ha_state(True)

    async def async_close_valve(self) -> None:
        """Close the valve."""
        self._ads_hub.write_by_name(self._ads_var, False, pyads.PLCTYPE_BOOL)
        self._attr_is_closed = True
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Retrieve the latest state from the ADS device."""
        # Read the valve state from the ADS device
        state_value = self._ads_hub.read_by_name(self._ads_var, pyads.PLCTYPE_BOOL)
        self._attr_is_closed = not state_value

        self.async_write_ha_state()
