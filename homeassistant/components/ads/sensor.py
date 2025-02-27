"""Support for ADS sensors."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    STATE_CLASSES_SCHEMA as SENSOR_STATE_CLASSES_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from .const import (
    ADS_TYPEMAP,
    CONF_ADS_FIELDS,
    CONF_ADS_HUB,
    CONF_ADS_HUB_DEFAULT,
    CONF_ADS_SYMBOLS,
    CONF_ADS_TEMPLATE,
    DOMAIN,
    STATE_KEY_STATE,
    AdsDiscoveryKeys,
    AdsSensorKeys,
    AdsType,
)
from .entity import AdsEntity
from .hub import AdsHub

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_HUB, default=CONF_ADS_HUB_DEFAULT): cv.string,
        vol.Optional(AdsSensorKeys.VAR): cv.string,
        vol.Optional(AdsSensorKeys.FACTOR): vol.Coerce(int),
        vol.Optional(AdsSensorKeys.TYPE, default=AdsType.INT): vol.All(
            vol.Coerce(AdsType),
            vol.In(
                [
                    AdsType.BOOL,
                    AdsType.BYTE,
                    AdsType.INT,
                    AdsType.UINT,
                    AdsType.SINT,
                    AdsType.USINT,
                    AdsType.DINT,
                    AdsType.UDINT,
                    AdsType.WORD,
                    AdsType.DWORD,
                    AdsType.LREAL,
                    AdsType.REAL,
                ]
            ),
        ),
        vol.Optional(AdsSensorKeys.NAME, default=AdsSensorKeys.DEFAULT_NAME): cv.string,
        vol.Optional(AdsSensorKeys.DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
        vol.Optional(AdsSensorKeys.STATE_CLASS): SENSOR_STATE_CLASSES_SCHEMA,
        vol.Optional(AdsSensorKeys.UNIT_OF_MEASUREMENT): cv.string,
    }
)


def _int_to_sensor_device_class(value: int) -> SensorDeviceClass | None:
    """Map integer values to SensorDeviceClass enums."""
    mapping = {
        0: None,
        1: SensorDeviceClass.APPARENT_POWER,
        2: SensorDeviceClass.AQI,
        3: SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        4: SensorDeviceClass.BATTERY,
        5: SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION,
        6: SensorDeviceClass.CO,
        7: SensorDeviceClass.CO2,
        8: SensorDeviceClass.CONDUCTIVITY,
        9: SensorDeviceClass.CURRENT,
        10: SensorDeviceClass.DATA_RATE,
        11: SensorDeviceClass.DATA_SIZE,
        12: SensorDeviceClass.DISTANCE,
        13: SensorDeviceClass.DURATION,
        14: SensorDeviceClass.ENERGY,
        15: SensorDeviceClass.ENERGY_STORAGE,
        16: SensorDeviceClass.FREQUENCY,
        17: SensorDeviceClass.GAS,
        18: SensorDeviceClass.HUMIDITY,
        19: SensorDeviceClass.ILLUMINANCE,
        20: SensorDeviceClass.IRRADIANCE,
        21: SensorDeviceClass.MOISTURE,
        22: SensorDeviceClass.MONETARY,
        23: SensorDeviceClass.NITROGEN_DIOXIDE,
        24: SensorDeviceClass.NITROGEN_MONOXIDE,
        25: SensorDeviceClass.NITROUS_OXIDE,
        26: SensorDeviceClass.OZONE,
        27: SensorDeviceClass.PH,
        28: SensorDeviceClass.PM1,
        29: SensorDeviceClass.PM10,
        30: SensorDeviceClass.PM25,
        31: SensorDeviceClass.POWER_FACTOR,
        32: SensorDeviceClass.POWER,
        33: SensorDeviceClass.PRECIPITATION,
        34: SensorDeviceClass.PRECIPITATION_INTENSITY,
        35: SensorDeviceClass.PRESSURE,
        36: SensorDeviceClass.REACTIVE_POWER,
        37: SensorDeviceClass.SIGNAL_STRENGTH,
        38: SensorDeviceClass.SOUND_PRESSURE,
        39: SensorDeviceClass.SPEED,
        40: SensorDeviceClass.SULPHUR_DIOXIDE,
        41: SensorDeviceClass.TEMPERATURE,
        42: SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        43: SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        44: SensorDeviceClass.VOLTAGE,
        45: SensorDeviceClass.VOLUME,
        46: SensorDeviceClass.VOLUME_STORAGE,
        47: SensorDeviceClass.VOLUME_FLOW_RATE,
        48: SensorDeviceClass.WATER,
        49: SensorDeviceClass.WEIGHT,
        50: SensorDeviceClass.WIND_SPEED,
    }
    return mapping.get(value)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform for ADS."""
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

            _ads_type = AdsType(_fields.get(AdsSensorKeys.TYPE))
            _ads_var = _path + "." + _fields.get(AdsSensorKeys.VAR)
            _factor: int | None = _fields.get(AdsSensorKeys.FACTOR)
            _unit_of_measurement = _fields.get(AdsSensorKeys.UNIT_OF_MEASUREMENT)
            _state_class = SensorStateClass(_fields.get(AdsSensorKeys.STATE_CLASS))
            _device_class = _int_to_sensor_device_class(_device_type)

            _entities.append(
                AdsSensor(
                    ads_hub=_ads_hub,
                    ads_var=_ads_var,
                    ads_type=_ads_type,
                    name=_name,
                    factor=_factor,
                    device_class=_device_class,
                    state_class=_state_class,
                    unit_of_measurement=_unit_of_measurement,
                )
            )

        add_entities(_entities)
        return

    hub_name: str = config[CONF_ADS_HUB]
    hub_key = f"{DOMAIN}_{hub_name}"
    ads_hub = hass.data.get(hub_key)
    if not ads_hub:
        return

    name: str = config[AdsSensorKeys.NAME]
    ads_var: str = config[AdsSensorKeys.VAR]
    ads_type: AdsType = config[AdsSensorKeys.TYPE]
    factor: int | None = config.get(AdsSensorKeys.FACTOR)
    device_class: SensorDeviceClass | None = config.get(AdsSensorKeys.DEVICE_CLASS)
    state_class: SensorStateClass | None = config.get(AdsSensorKeys.STATE_CLASS)
    unit_of_measurement: str | None = config.get(AdsSensorKeys.UNIT_OF_MEASUREMENT)

    add_entities(
        [
            AdsSensor(
                ads_hub=ads_hub,
                ads_var=ads_var,
                ads_type=ads_type,
                name=name,
                factor=factor,
                device_class=device_class,
                state_class=state_class,
                unit_of_measurement=unit_of_measurement,
            )
        ]
    )


class AdsSensor(AdsEntity, SensorEntity):
    """Representation of an ADS sensor entity."""

    def __init__(
        self,
        ads_hub: AdsHub,
        ads_var: str,
        ads_type: AdsType,
        name: str,
        factor: int | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        unit_of_measurement: str | None,
    ) -> None:
        """Initialize AdsSensor entity."""
        super().__init__(ads_hub, name, ads_var)
        self._ads_type = ads_type
        self._factor = factor
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit_of_measurement

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        await self.async_initialize_device(
            self._ads_var,
            ADS_TYPEMAP[self._ads_type],
            STATE_KEY_STATE,
            self._factor,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        return self._state_dict[STATE_KEY_STATE]
