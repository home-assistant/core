"""Support for ADS covers with tilt functionality."""

from __future__ import annotations

from typing import Any

import pyads
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as COVER_PLATFORM_SCHEMA,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ADS_TYPEMAP,
    CONF_ADS_FIELDS,
    CONF_ADS_HUB,
    CONF_ADS_HUB_DEFAULT,
    CONF_ADS_SYMBOLS,
    CONF_ADS_TEMPLATE,
    DOMAIN,
    STATE_KEY_POSITION,
    STATE_KEY_STATE,
    STATE_KEY_TILT_POSITION,
    AdsCoverKeys,
    AdsDiscoveryKeys,
    AdsType,
)
from .entity import AdsEntity
from .hub import AdsHub

PLATFORM_SCHEMA = COVER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_HUB, default=CONF_ADS_HUB_DEFAULT): cv.string,
        vol.Required(AdsCoverKeys.VAR): cv.string,
        vol.Optional(AdsCoverKeys.TYPE, default=AdsType.BYTE): vol.All(
            vol.Coerce(AdsType),
            vol.In(
                [
                    AdsType.BYTE,
                    AdsType.INT,
                    AdsType.UINT,
                    AdsType.SINT,
                    AdsType.USINT,
                    AdsType.DINT,
                    AdsType.UDINT,
                    AdsType.WORD,
                    AdsType.DWORD,
                ]
            ),
        ),
        vol.Optional(AdsCoverKeys.VAR_POSITION): cv.string,
        vol.Optional(AdsCoverKeys.VAR_SET_POSITION): cv.string,
        vol.Optional(AdsCoverKeys.VAL_OPEN_POSITION, default=100): vol.Coerce(int),
        vol.Optional(AdsCoverKeys.VAL_CLOSE_POSITION, default=0): vol.Coerce(int),
        vol.Optional(AdsCoverKeys.VAR_CLOSE): cv.string,
        vol.Optional(AdsCoverKeys.VAR_OPEN): cv.string,
        vol.Optional(AdsCoverKeys.VAR_STOP): cv.string,
        vol.Optional(AdsCoverKeys.VAR_TILT): cv.string,
        vol.Optional(AdsCoverKeys.VAL_OPEN_TILT, default=0): vol.Coerce(int),
        vol.Optional(AdsCoverKeys.VAL_CLOSE_TILT, default=100): vol.Coerce(int),
        vol.Optional(AdsCoverKeys.VAR_SET_TILT): cv.string,
        vol.Optional(AdsCoverKeys.VAR_OPEN_TILT): cv.string,
        vol.Optional(AdsCoverKeys.VAR_CLOSE_TILT): cv.string,
        vol.Optional(AdsCoverKeys.NAME, default=AdsCoverKeys.DEFAULT_NAME): cv.string,
        vol.Optional(AdsCoverKeys.DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)


def _device_class_to_int(device_class: CoverDeviceClass) -> int | None:
    """Map CoverDeviceClass enums to integer values."""
    mapping = {
        CoverDeviceClass.AWNING: 1,
        CoverDeviceClass.BLIND: 2,
        CoverDeviceClass.CURTAIN: 3,
        CoverDeviceClass.DAMPER: 4,
        CoverDeviceClass.DOOR: 5,
        CoverDeviceClass.GARAGE: 6,
        CoverDeviceClass.GATE: 7,
        CoverDeviceClass.SHADE: 8,
        CoverDeviceClass.SHUTTER: 9,
        CoverDeviceClass.WINDOW: 10,
    }
    return mapping.get(device_class)


def _int_to_device_class(value: int) -> CoverDeviceClass | None:
    """Map integer values to CoverDeviceClass enums."""
    mapping = {
        1: CoverDeviceClass.AWNING,
        2: CoverDeviceClass.BLIND,
        3: CoverDeviceClass.CURTAIN,
        4: CoverDeviceClass.DAMPER,
        5: CoverDeviceClass.DOOR,
        6: CoverDeviceClass.GARAGE,
        7: CoverDeviceClass.GATE,
        8: CoverDeviceClass.SHADE,
        9: CoverDeviceClass.SHUTTER,
        10: CoverDeviceClass.WINDOW,
    }
    return mapping.get(value)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the cover platform for ADS."""

    if discovery_info is not None:
        _hub_name = discovery_info.get(CONF_ADS_HUB)
        _hub_key = f"{DOMAIN}_{_hub_name}"
        _ads_hub = hass.data.get(_hub_key)
        if not _ads_hub:
            return

        _entities = []
        _symbols = discovery_info.get(CONF_ADS_SYMBOLS, [])
        _template = discovery_info.get(CONF_ADS_TEMPLATE, {})
        _fields = _template.get(CONF_ADS_FIELDS, {})

        for _symbol in _symbols:
            _path = _symbol.get(AdsDiscoveryKeys.ADSPATH)
            _name = _symbol.get(AdsDiscoveryKeys.NAME)
            _device_type = _symbol.get(AdsDiscoveryKeys.DEVICE_TYPE)
            if not _name or not _device_type:
                continue

            _ads_type = AdsType(_fields.get(AdsCoverKeys.TYPE))
            _device_class = _int_to_device_class(_device_type)

            _ads_val_open_position = int(_fields.get(AdsCoverKeys.VAL_OPEN_POSITION))
            _ads_val_close_position = int(_fields.get(AdsCoverKeys.VAL_CLOSE_POSITION))
            _ads_val_open_tilt = int(_fields.get(AdsCoverKeys.VAL_OPEN_TILT))
            _ads_val_close_tilt = int(_fields.get(AdsCoverKeys.VAL_CLOSE_TILT))

            _ads_var_is_closed = _path + "." + _fields.get(AdsCoverKeys.VAR)
            _ads_var_open = _path + "." + _fields.get(AdsCoverKeys.VAR_OPEN)
            _ads_var_close = _path + "." + _fields.get(AdsCoverKeys.VAR_CLOSE)
            _ads_var_stop = _path + "." + _fields.get(AdsCoverKeys.VAR_STOP)
            _ads_var_position = _path + "." + _fields.get(AdsCoverKeys.VAR_POSITION)
            _ads_var_set_position = (
                _path + "." + _fields.get(AdsCoverKeys.VAR_SET_POSITION)
            )

            _has_tilt = _device_class == CoverDeviceClass.SHADE
            _ads_var_tilt = (
                _path + "." + _fields.get(AdsCoverKeys.VAR_TILT) if _has_tilt else None
            )
            _ads_var_set_tilt = (
                _path + "." + _fields.get(AdsCoverKeys.VAR_SET_TILT)
                if _has_tilt
                else None
            )
            _ads_var_open_tilt = (
                _path + "." + _fields.get(AdsCoverKeys.VAR_OPEN_TILT)
                if _has_tilt
                else None
            )
            _ads_var_close_tilt = (
                _path + "." + _fields.get(AdsCoverKeys.VAR_CLOSE_TILT)
                if _has_tilt
                else None
            )

            _entities.append(
                AdsCover(
                    ads_hub=_ads_hub,
                    name=_name,
                    ads_type=_ads_type,
                    ads_var_is_closed=_ads_var_is_closed,
                    ads_var_open=_ads_var_open,
                    ads_var_close=_ads_var_close,
                    ads_var_stop=_ads_var_stop,
                    ads_var_position=_ads_var_position,
                    ads_var_set_position=_ads_var_set_position,
                    ads_val_close_position=_ads_val_close_position,
                    ads_val_open_position=_ads_val_open_position,
                    ads_var_tilt=_ads_var_tilt,
                    ads_var_set_tilt=_ads_var_set_tilt,
                    ads_val_open_tilt=_ads_val_open_tilt,
                    ads_val_close_tilt=_ads_val_close_tilt,
                    ads_var_open_tilt=_ads_var_open_tilt,
                    ads_var_close_tilt=_ads_var_close_tilt,
                    device_class=_device_class,
                )
            )

        add_entities(_entities)
        return

    hub_name: str = config[CONF_ADS_HUB]
    hub_key = f"{DOMAIN}_{hub_name}"
    ads_hub = hass.data.get(hub_key)
    if not ads_hub:
        return

    name: str = config[AdsCoverKeys.NAME]
    ads_type: AdsType = config[AdsCoverKeys.TYPE]
    device_class: CoverDeviceClass | None = config.get(AdsCoverKeys.DEVICE_CLASS)

    ads_val_open_position: int = config[AdsCoverKeys.VAL_OPEN_POSITION]
    ads_val_close_position: int = config[AdsCoverKeys.VAL_CLOSE_POSITION]
    ads_val_open_tilt: int = config[AdsCoverKeys.VAL_OPEN_TILT]
    ads_val_close_tilt: int = config[AdsCoverKeys.VAL_CLOSE_TILT]

    ads_var_is_closed: str = config[AdsCoverKeys.VAR]
    ads_var_open: str | None = config.get(AdsCoverKeys.VAR_OPEN)
    ads_var_close: str | None = config.get(AdsCoverKeys.VAR_CLOSE)
    ads_var_stop: str | None = config.get(AdsCoverKeys.VAR_STOP)
    ads_var_position: str | None = config.get(AdsCoverKeys.VAR_POSITION)
    ads_var_set_position: str | None = config.get(AdsCoverKeys.VAR_SET_POSITION)
    ads_var_tilt: str | None = config.get(AdsCoverKeys.VAR_TILT)
    ads_var_set_tilt: str | None = config.get(AdsCoverKeys.VAR_SET_TILT)
    ads_var_open_tilt: str | None = config.get(AdsCoverKeys.VAR_OPEN_TILT)
    ads_var_close_tilt: str | None = config.get(AdsCoverKeys.VAR_CLOSE_TILT)

    add_entities(
        [
            AdsCover(
                ads_hub=ads_hub,
                name=name,
                ads_type=ads_type,
                ads_var_is_closed=ads_var_is_closed,
                ads_var_open=ads_var_open,
                ads_var_close=ads_var_close,
                ads_var_stop=ads_var_stop,
                ads_var_position=ads_var_position,
                ads_var_set_position=ads_var_set_position,
                ads_val_close_position=ads_val_close_position,
                ads_val_open_position=ads_val_open_position,
                ads_var_tilt=ads_var_tilt,
                ads_var_set_tilt=ads_var_set_tilt,
                ads_val_open_tilt=ads_val_open_tilt,
                ads_val_close_tilt=ads_val_close_tilt,
                ads_var_open_tilt=ads_var_open_tilt,
                ads_var_close_tilt=ads_var_close_tilt,
                device_class=device_class,
            )
        ]
    )


class AdsCover(AdsEntity, CoverEntity):
    """Representation of ADS cover with tilt functionality."""

    def __init__(
        self,
        ads_hub: AdsHub,
        ads_type: AdsType,
        name: str,
        ads_var_is_closed: str,
        ads_var_open: str | None,
        ads_var_close: str | None,
        ads_var_stop: str | None,
        ads_var_position: str | None,
        ads_var_set_position: str | None,
        ads_val_close_position: int,
        ads_val_open_position: int,
        ads_var_tilt: str | None,
        ads_var_set_tilt: str | None,
        ads_val_open_tilt: int,
        ads_val_close_tilt: int,
        ads_var_open_tilt: str | None,
        ads_var_close_tilt: str | None,
        device_class: CoverDeviceClass | None,
    ) -> None:
        """Initialize AdsCover entity."""
        super().__init__(ads_hub, name, ads_var_is_closed)

        self._ads_type = ads_type
        self._attr_device_class = device_class
        self._ads_val_open_position = ads_val_open_position
        self._ads_val_close_position = ads_val_close_position
        self._ads_val_open_tilt = ads_val_open_tilt
        self._ads_val_close_tilt = ads_val_close_tilt

        self._ads_var_is_closed = ads_var_is_closed
        self._ads_var_open = ads_var_open
        self._ads_var_close = ads_var_close
        self._ads_var_stop = ads_var_stop
        self._ads_var_position = ads_var_position
        self._ads_var_set_position = ads_var_set_position
        self._ads_var_tilt = ads_var_tilt
        self._ads_var_set_tilt = ads_var_set_tilt
        self._ads_var_open_tilt = ads_var_open_tilt
        self._ads_var_close_tilt = ads_var_close_tilt

        self._state_dict[STATE_KEY_POSITION] = None
        self._state_dict[STATE_KEY_TILT_POSITION] = None

        # Initialize supported features
        self._attr_supported_features: CoverEntityFeature = CoverEntityFeature(0)

        if self._ads_var_open is not None:
            self._attr_supported_features |= int(CoverEntityFeature.OPEN)
        if self._ads_var_close is not None:
            self._attr_supported_features |= int(CoverEntityFeature.CLOSE)
        if self._ads_var_stop is not None:
            self._attr_supported_features |= int(CoverEntityFeature.STOP)
        if self._ads_var_set_position is not None:
            self._attr_supported_features |= int(CoverEntityFeature.SET_POSITION)
        if self._ads_var_open_tilt is not None:
            self._attr_supported_features |= int(CoverEntityFeature.OPEN_TILT)
        if self._ads_var_close_tilt is not None:
            self._attr_supported_features |= int(CoverEntityFeature.CLOSE_TILT)
        if self._ads_var_set_tilt is not None:
            self._attr_supported_features |= int(CoverEntityFeature.SET_TILT_POSITION)

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        if self._ads_var_is_closed is not None:
            await self.async_initialize_device(
                self._ads_var_is_closed, pyads.PLCTYPE_BOOL, STATE_KEY_STATE
            )

        if self._ads_var_position is not None:
            await self.async_initialize_device(
                self._ads_var_position, ADS_TYPEMAP[self._ads_type], STATE_KEY_POSITION
            )

        if self._ads_var_tilt is not None:
            await self.async_initialize_device(
                self._ads_var_tilt, ADS_TYPEMAP[self._ads_type], STATE_KEY_TILT_POSITION
            )

    def scale_value(
        self, value: int, src_min: int, src_max: int, dest_min: int, dest_max: int
    ) -> int:
        """Scale a value from one range (src_min-src_max) to another (dest_min-dest_max)."""
        if src_min == src_max:
            return dest_min
        scale_factor = (value - src_min) / (src_max - src_min)
        return int(dest_min + scale_factor * (dest_max - dest_min))

    def scale_position_to_ads(self, hass_position: int) -> int:
        """Scale position from Home Assistant (100-0) to ADS range."""
        return self.scale_value(
            hass_position,
            100,
            0,
            self._ads_val_open_position,
            self._ads_val_close_position,
        )

    def scale_position_from_ads(self, ads_position: int) -> int:
        """Scale position from ADS range to Home Assistant (100-0)."""
        return self.scale_value(
            ads_position,
            self._ads_val_open_position,
            self._ads_val_close_position,
            100,
            0,
        )

    def scale_tilt_to_ads(self, hass_tilt: int) -> int:
        """Scale tilt from Home Assistant (0-100) to ADS range."""
        return self.scale_value(
            hass_tilt, 0, 100, self._ads_val_open_tilt, self._ads_val_close_tilt
        )

    def scale_tilt_from_ads(self, ads_tilt: int) -> int:
        """Scale tilt from ADS range to Home Assistant (0-100)."""
        return self.scale_value(
            ads_tilt, self._ads_val_open_tilt, self._ads_val_close_tilt, 0, 100
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
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        ads_position = self._state_dict[STATE_KEY_POSITION]
        if ads_position is not None:
            return self.scale_position_from_ads(ads_position)
        return None

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        ads_tilt = self._state_dict[STATE_KEY_TILT_POSITION]
        if ads_tilt is not None:
            return self.scale_tilt_from_ads(ads_tilt)
        return None

    def set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        position = kwargs[ATTR_POSITION]
        if self._ads_var_set_position is not None:
            ads_position = self.scale_position_to_ads(position)
            self._ads_hub.write_by_name(
                self._ads_var_set_position, ads_position, ADS_TYPEMAP[self._ads_type]
            )

    def set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set the tilt position."""
        tilt_position = kwargs[ATTR_TILT_POSITION]
        if self._ads_var_set_tilt is not None:
            ads_tilt = self.scale_tilt_to_ads(tilt_position)
            self._ads_hub.write_by_name(
                self._ads_var_set_tilt, ads_tilt, ADS_TYPEMAP[self._ads_type]
            )

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self._ads_var_open is not None:
            self._ads_hub.write_by_name(self._ads_var_open, True, pyads.PLCTYPE_BOOL)

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if self._ads_var_close is not None:
            self._ads_hub.write_by_name(self._ads_var_close, True, pyads.PLCTYPE_BOOL)

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        if self._ads_var_stop is not None:
            self._ads_hub.write_by_name(self._ads_var_stop, True, pyads.PLCTYPE_BOOL)

    def open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the tilt of the cover."""
        if self._ads_var_open_tilt is not None:
            self._ads_hub.write_by_name(
                self._ads_var_open_tilt, True, pyads.PLCTYPE_BOOL
            )

    def close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the tilt of the cover."""
        if self._ads_var_close_tilt is not None:
            self._ads_hub.write_by_name(
                self._ads_var_close_tilt, True, pyads.PLCTYPE_BOOL
            )
