"""Support for ADS binary sensors."""

from __future__ import annotations

import pyads
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_ADS_FIELDS,
    CONF_ADS_HUB,
    CONF_ADS_HUB_DEFAULT,
    CONF_ADS_SYMBOLS,
    CONF_ADS_TEMPLATE,
    DOMAIN,
    STATE_KEY_STATE,
    AdsBinarySensorKeys,
    AdsDiscoveryKeys,
)
from .entity import AdsEntity
from .hub import AdsHub

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_HUB, default=CONF_ADS_HUB_DEFAULT): cv.string,
        vol.Required(AdsBinarySensorKeys.VAR): cv.string,
        vol.Optional(
            AdsBinarySensorKeys.NAME, default=AdsBinarySensorKeys.DEFAULT_NAME
        ): cv.string,
        vol.Optional(AdsBinarySensorKeys.DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)


def _int_to_binary_sensor_device_class(value: int) -> BinarySensorDeviceClass | None:
    """Map integer values to BinarySensorDeviceClass enums."""
    mapping = {
        0: None,
        1: BinarySensorDeviceClass.BATTERY,
        2: BinarySensorDeviceClass.BATTERY_CHARGING,
        3: BinarySensorDeviceClass.CO,
        4: BinarySensorDeviceClass.COLD,
        5: BinarySensorDeviceClass.CONNECTIVITY,
        6: BinarySensorDeviceClass.DOOR,
        7: BinarySensorDeviceClass.GARAGE_DOOR,
        8: BinarySensorDeviceClass.GAS,
        9: BinarySensorDeviceClass.HEAT,
        10: BinarySensorDeviceClass.LIGHT,
        11: BinarySensorDeviceClass.LOCK,
        12: BinarySensorDeviceClass.MOISTURE,
        13: BinarySensorDeviceClass.MOTION,
        14: BinarySensorDeviceClass.MOVING,
        15: BinarySensorDeviceClass.OCCUPANCY,
        16: BinarySensorDeviceClass.OPENING,
        17: BinarySensorDeviceClass.PLUG,
        18: BinarySensorDeviceClass.POWER,
        19: BinarySensorDeviceClass.PRESENCE,
        20: BinarySensorDeviceClass.PROBLEM,
        21: BinarySensorDeviceClass.RUNNING,
        22: BinarySensorDeviceClass.SAFETY,
        23: BinarySensorDeviceClass.SMOKE,
        24: BinarySensorDeviceClass.SOUND,
        25: BinarySensorDeviceClass.TAMPER,
        26: BinarySensorDeviceClass.UPDATE,
        27: BinarySensorDeviceClass.VIBRATION,
        28: BinarySensorDeviceClass.WINDOW,
    }
    return mapping.get(value)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Binary Sensor platform for ADS."""
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
            _device_type = _symbol.get(AdsDiscoveryKeys.DEVICE_TYPE)
            _path = _symbol.get(AdsDiscoveryKeys.ADSPATH)
            _name = _symbol.get(AdsDiscoveryKeys.NAME)
            if not _name or not _device_type:
                continue

            _ads_var_state = _path + "." + _fields.get(AdsBinarySensorKeys.VAR)
            _device_class = _int_to_binary_sensor_device_class(_device_type)

            _entities.append(
                AdsBinarySensor(
                    ads_hub=_ads_hub,
                    name=_name,
                    ads_var=_ads_var_state,
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

    ads_var: str = config[AdsBinarySensorKeys.VAR]
    name: str = config[AdsBinarySensorKeys.NAME]
    device_class: BinarySensorDeviceClass | None = config.get(
        AdsBinarySensorKeys.DEVICE_CLASS
    )

    add_entities(
        [
            AdsBinarySensor(
                ads_hub=ads_hub,
                name=name,
                ads_var=ads_var,
                device_class=device_class,
            )
        ]
    )


class AdsBinarySensor(AdsEntity, BinarySensorEntity):
    """Representation of ADS binary sensors."""

    def __init__(
        self,
        ads_hub: AdsHub,
        name: str,
        ads_var: str,
        device_class: BinarySensorDeviceClass | None,
    ) -> None:
        """Initialize ADS binary sensor."""
        super().__init__(ads_hub, name, ads_var)
        self._attr_device_class = device_class

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, pyads.PLCTYPE_BOOL)

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return self._state_dict[STATE_KEY_STATE]
