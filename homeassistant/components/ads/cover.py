"""Support for ADS covers."""

from typing import Any, override

import probatio
import pyads

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as COVER_PLATFORM_SCHEMA,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_ADS_VAR, STATE_KEY_STATE
from .entity import AdsEntity
from .hub import AdsHub, async_get_hub

DEFAULT_NAME = "ADS Cover"

CONF_ADS_VAR_SET_POS = "adsvar_set_position"
CONF_ADS_VAR_OPEN = "adsvar_open"
CONF_ADS_VAR_CLOSE = "adsvar_close"
CONF_ADS_VAR_STOP = "adsvar_stop"
CONF_ADS_VAR_POSITION = "adsvar_position"

STATE_KEY_POSITION = "position"

PLATFORM_SCHEMA = COVER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_ADS_VAR): cv.string,
        probatio.Optional(CONF_ADS_VAR_POSITION): cv.string,
        probatio.Optional(CONF_ADS_VAR_SET_POS): cv.string,
        probatio.Optional(CONF_ADS_VAR_CLOSE): cv.string,
        probatio.Optional(CONF_ADS_VAR_OPEN): cv.string,
        probatio.Optional(CONF_ADS_VAR_STOP): cv.string,
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the cover platform for ADS."""
    ads_hub = async_get_hub(hass)

    ads_var_is_closed: str = config[CONF_ADS_VAR]
    ads_var_position: str | None = config.get(CONF_ADS_VAR_POSITION)
    ads_var_pos_set: str | None = config.get(CONF_ADS_VAR_SET_POS)
    ads_var_open: str | None = config.get(CONF_ADS_VAR_OPEN)
    ads_var_close: str | None = config.get(CONF_ADS_VAR_CLOSE)
    ads_var_stop: str | None = config.get(CONF_ADS_VAR_STOP)
    name: str = config[CONF_NAME]
    device_class: CoverDeviceClass | None = config.get(CONF_DEVICE_CLASS)

    async_add_entities(
        [
            AdsCover(
                ads_hub,
                ads_var_is_closed,
                ads_var_position,
                ads_var_pos_set,
                ads_var_open,
                ads_var_close,
                ads_var_stop,
                name,
                device_class,
            )
        ]
    )


class AdsCover(AdsEntity, CoverEntity):
    """Representation of ADS cover."""

    def __init__(
        self,
        ads_hub: AdsHub,
        ads_var_is_closed: str,
        ads_var_position: str | None,
        ads_var_pos_set: str | None,
        ads_var_open: str | None,
        ads_var_close: str | None,
        ads_var_stop: str | None,
        name: str,
        device_class: CoverDeviceClass | None,
    ) -> None:
        """Initialize AdsCover entity."""
        super().__init__(ads_hub, name, ads_var_is_closed)
        self._state_dict[STATE_KEY_POSITION] = None
        self._ads_var_position = ads_var_position
        self._ads_var_pos_set = ads_var_pos_set
        self._ads_var_open = ads_var_open
        self._ads_var_close = ads_var_close
        self._ads_var_stop = ads_var_stop
        self._attr_device_class = device_class
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )
        if ads_var_stop is not None:
            self._attr_supported_features |= CoverEntityFeature.STOP
        if ads_var_pos_set is not None:
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

    @override
    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, pyads.PLCTYPE_BOOL)

        if self._ads_var_position is not None:
            await self.async_initialize_device(
                self._ads_var_position, pyads.PLCTYPE_BYTE, STATE_KEY_POSITION
            )

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self._state_dict[STATE_KEY_STATE]

    @property
    @override
    def current_cover_position(self) -> int:
        """Return current position of cover."""
        return self._state_dict[STATE_KEY_POSITION]

    @override
    def stop_cover(self, **kwargs: Any) -> None:
        """Fire the stop action."""
        if self._ads_var_stop:
            self._ads_hub.write_by_name(self._ads_var_stop, True, pyads.PLCTYPE_BOOL)

    @override
    def set_cover_position(self, **kwargs: Any) -> None:
        """Set cover position."""
        position = kwargs[ATTR_POSITION]
        if self._ads_var_pos_set is not None:
            self._ads_hub.write_by_name(
                self._ads_var_pos_set, position, pyads.PLCTYPE_BYTE
            )

    @override
    def open_cover(self, **kwargs: Any) -> None:
        """Move the cover up."""
        if self._ads_var_open is not None:
            self._ads_hub.write_by_name(self._ads_var_open, True, pyads.PLCTYPE_BOOL)
        elif self._ads_var_pos_set is not None:
            self.set_cover_position(position=100)

    @override
    def close_cover(self, **kwargs: Any) -> None:
        """Move the cover down."""
        if self._ads_var_close is not None:
            self._ads_hub.write_by_name(self._ads_var_close, True, pyads.PLCTYPE_BOOL)
        elif self._ads_var_pos_set is not None:
            self.set_cover_position(position=0)

    @property
    @override
    def available(self) -> bool:
        """Return False if state has not been updated yet."""
        return (
            self._state_dict[STATE_KEY_STATE] is not None
            or self._state_dict[STATE_KEY_POSITION] is not None
        )
