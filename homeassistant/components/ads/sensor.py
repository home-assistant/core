"""Support for ADS sensors."""

from __future__ import annotations

from datetime import UTC, date, datetime

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from .. import ads
from . import (
    ADS_TYPEMAP,
    CONF_ADS_FACTOR,
    CONF_ADS_TYPE,
    CONF_ADS_VAR,
    STATE_KEY_STATE,
    AdsEntity,
)

DEFAULT_NAME = "ADS sensor"
DEFAULT_DEVICE_CLASS = SensorDeviceClass.ENUM

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADS_VAR): cv.string,
        vol.Optional(CONF_ADS_FACTOR): cv.positive_int,
        vol.Optional(CONF_ADS_TYPE, default=ads.ADSTYPE_INT): vol.In(
            [
                ads.ADSTYPE_BOOL,
                ads.ADSTYPE_BYTE,
                ads.ADSTYPE_INT,
                ads.ADSTYPE_UINT,
                ads.ADSTYPE_SINT,
                ads.ADSTYPE_USINT,
                ads.ADSTYPE_DINT,
                ads.ADSTYPE_UDINT,
                ads.ADSTYPE_WORD,
                ads.ADSTYPE_DWORD,
                ads.ADSTYPE_LREAL,
                ads.ADSTYPE_REAL,
                ads.ADSTYPE_DATE,
                ads.ADSTYPE_TIME,
                ads.ADSTYPE_DATE_AND_TIME,
                ads.ADSTYPE_TOD,
            ]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=""): cv.string,
        vol.Optional("device_class", default=DEFAULT_DEVICE_CLASS): vol.In(
            [device_class.value for device_class in SensorDeviceClass]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an ADS sensor device."""
    ads_hub = hass.data.get(ads.DATA_ADS)

    ads_var = config[CONF_ADS_VAR]
    ads_type = config[CONF_ADS_TYPE]
    name = config[CONF_NAME]
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
    factor = config.get(CONF_ADS_FACTOR)
    device_class_str = config.get("device_class")

    device_class = SensorDeviceClass(device_class_str) if device_class_str else None

    entity = AdsSensor(
        ads_hub, ads_var, ads_type, name, unit_of_measurement, factor, device_class
    )

    add_entities([entity])


class AdsSensor(AdsEntity, SensorEntity):
    """Representation of an ADS sensor entity."""

    def __init__(
        self,
        ads_hub,
        ads_var,
        ads_type,
        name,
        unit_of_measurement,
        factor,
        device_class,
    ):
        """Initialize AdsSensor entity."""
        super().__init__(ads_hub, name, ads_var)
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._ads_type = ads_type
        self._factor = factor
        self._device_class = device_class

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the class of this sensor."""
        return self._device_class

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        await self.async_initialize_device(
            self._ads_var,
            ADS_TYPEMAP[self._ads_type],
            STATE_KEY_STATE,
            self._factor,
        )

    @property
    def native_value(self) -> StateType | datetime | date:
        """Return the state of the device."""
        state = self._state_dict.get(STATE_KEY_STATE)

        if self._device_class == SensorDeviceClass.TIMESTAMP and isinstance(state, int):
            # Convert integer timestamp to datetime object
            return datetime.fromtimestamp(state, tz=UTC)
        if self._device_class == SensorDeviceClass.DATE and isinstance(state, int):
            # Convert integer timestamp to datetime object for date only
            dt = datetime.fromtimestamp(state, tz=UTC)
            return dt.date()
        return state
