"""Support for ADS valves."""

from typing import override

import probatio
import pyads

from homeassistant.components.valve import (
    DEVICE_CLASSES_SCHEMA as VALVE_DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as VALVE_PLATFORM_SCHEMA,
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_ADS_VAR, STATE_KEY_STATE
from .entity import AdsEntity
from .hub import AdsHub, async_get_hub

DEFAULT_NAME = "ADS valve"

PLATFORM_SCHEMA = VALVE_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_ADS_VAR): cv.string,
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_DEVICE_CLASS): VALVE_DEVICE_CLASSES_SCHEMA,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an ADS valve device."""
    ads_hub = async_get_hub(hass)

    ads_var: str = config[CONF_ADS_VAR]
    name: str = config[CONF_NAME]
    device_class: ValveDeviceClass | None = config.get(CONF_DEVICE_CLASS)

    entity = AdsValve(ads_hub, ads_var, name, device_class)

    async_add_entities([entity])


class AdsValve(AdsEntity, ValveEntity):
    """Representation of an ADS valve entity."""

    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    def __init__(
        self,
        ads_hub: AdsHub,
        ads_var: str,
        name: str,
        device_class: ValveDeviceClass | None,
    ) -> None:
        """Initialize AdsValve entity."""
        super().__init__(ads_hub, name, ads_var)
        self._attr_device_class = device_class
        self._attr_reports_position = False

    @override
    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, pyads.PLCTYPE_BOOL)

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the valve is closed."""
        if (state := self._state_dict[STATE_KEY_STATE]) is None:
            return None
        return not state

    @override
    def open_valve(self, **kwargs) -> None:
        """Open the valve."""
        self._ads_hub.write_by_name(self._ads_var, True, pyads.PLCTYPE_BOOL)

    @override
    def close_valve(self, **kwargs) -> None:
        """Close the valve."""
        self._ads_hub.write_by_name(self._ads_var, False, pyads.PLCTYPE_BOOL)
