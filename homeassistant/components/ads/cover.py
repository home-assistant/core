"""Support for ADS covers."""

from __future__ import annotations

from typing import Any

import pyads
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as COVER_PLATFORM_SCHEMA,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_ADS_VAR,
    CONF_ADS_VAR_POSITION,
    DATA_ADS,
    STATE_KEY_POSITION,
    STATE_KEY_STATE,
    AdsEntity,
)

DEFAULT_NAME = "ADS Cover"

CONF_ADS_VAR_SET_POS = "adsvar_set_position"
CONF_ADS_VAR_OPEN = "adsvar_open"
CONF_ADS_VAR_CLOSE = "adsvar_close"
CONF_ADS_VAR_STOP = "adsvar_stop"

PLATFORM_SCHEMA = COVER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_VAR): cv.string,
        vol.Optional(CONF_ADS_VAR_POSITION): cv.string,
        vol.Optional(CONF_ADS_VAR_SET_POS): cv.string,
        vol.Optional(CONF_ADS_VAR_CLOSE): cv.string,
        vol.Optional(CONF_ADS_VAR_OPEN): cv.string,
        vol.Optional(CONF_ADS_VAR_STOP): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the cover platform for ADS."""
    ads_hub = hass.data[DATA_ADS]

    ads_var_is_closed = config.get(CONF_ADS_VAR)
    ads_var_position = config.get(CONF_ADS_VAR_POSITION)
    ads_var_pos_set = config.get(CONF_ADS_VAR_SET_POS)
    ads_var_open = config.get(CONF_ADS_VAR_OPEN)
    ads_var_close = config.get(CONF_ADS_VAR_CLOSE)
    ads_var_stop = config.get(CONF_ADS_VAR_STOP)
    name = config[CONF_NAME]
    device_class = config.get(CONF_DEVICE_CLASS)

    add_entities(
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
        ads_hub,
        ads_var_is_closed,
        ads_var_position,
        ads_var_pos_set,
        ads_var_open,
        ads_var_close,
        ads_var_stop,
        name,
        device_class,
    ):
        """Initialize AdsCover entity."""
        super().__init__(ads_hub, name, ads_var_is_closed)
        if self._attr_unique_id is None:
            if ads_var_position is not None:
                self._attr_unique_id = ads_var_position
            elif ads_var_pos_set is not None:
                self._attr_unique_id = ads_var_pos_set
            elif ads_var_open is not None:
                self._attr_unique_id = ads_var_open

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

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        if self._ads_var is not None:
            await self.async_initialize_device(self._ads_var, pyads.PLCTYPE_BOOL)

        if self._ads_var_position is not None:
            await self.async_initialize_device(
                self._ads_var_position, pyads.PLCTYPE_BYTE, STATE_KEY_POSITION
            )

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._ads_var is not None:
            return self._state_dict[STATE_KEY_STATE]
        if self._ads_var_position is not None:
            return self._state_dict[STATE_KEY_POSITION] == 0
        return None

    @property
    def current_cover_position(self) -> int:
        """Return current position of cover."""
        return self._state_dict[STATE_KEY_POSITION]

    def stop_cover(self, **kwargs: Any) -> None:
        """Fire the stop action."""
        if self._ads_var_stop:
            self._ads_hub.write_by_name(self._ads_var_stop, True, pyads.PLCTYPE_BOOL)

    def set_cover_position(self, **kwargs: Any) -> None:
        """Set cover position."""
        position = kwargs[ATTR_POSITION]
        if self._ads_var_pos_set is not None:
            self._ads_hub.write_by_name(
                self._ads_var_pos_set, position, pyads.PLCTYPE_BYTE
            )

    def open_cover(self, **kwargs: Any) -> None:
        """Move the cover up."""
        if self._ads_var_open is not None:
            self._ads_hub.write_by_name(self._ads_var_open, True, pyads.PLCTYPE_BOOL)
        elif self._ads_var_pos_set is not None:
            self.set_cover_position(position=100)

    def close_cover(self, **kwargs: Any) -> None:
        """Move the cover down."""
        if self._ads_var_close is not None:
            self._ads_hub.write_by_name(self._ads_var_close, True, pyads.PLCTYPE_BOOL)
        elif self._ads_var_pos_set is not None:
            self.set_cover_position(position=0)

    @property
    def available(self) -> bool:
        """Return False if state has not been updated yet."""
        if self._ads_var is not None or self._ads_var_position is not None:
            return (
                self._state_dict[STATE_KEY_STATE] is not None
                or self._state_dict[STATE_KEY_POSITION] is not None
            )
        return True
