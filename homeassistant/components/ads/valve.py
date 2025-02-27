"""Support for ADS valves."""

from __future__ import annotations

import pyads
import voluptuous as vol

from homeassistant.components.valve import (
    DEVICE_CLASSES_SCHEMA as VALVE_DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as VALVE_PLATFORM_SCHEMA,
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
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
    AdsDiscoveryKeys,
    AdsValveKeys,
)
from .entity import AdsEntity
from .hub import AdsHub

PLATFORM_SCHEMA = VALVE_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_HUB, default=CONF_ADS_HUB_DEFAULT): cv.string,
        vol.Required(AdsValveKeys.VAR): cv.string,
        vol.Optional(AdsValveKeys.NAME, default=AdsValveKeys.DEFAULT_NAME): cv.string,
        vol.Optional(AdsValveKeys.DEVICE_CLASS): VALVE_DEVICE_CLASSES_SCHEMA,
    }
)


def _int_to_valve_device_class(value: int) -> ValveDeviceClass | None:
    """Map integer values to ValveDeviceClass enums."""
    mapping = {
        0: None,
        1: ValveDeviceClass.GAS,
        2: ValveDeviceClass.WATER,
    }
    return mapping.get(value)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an ADS valve device."""

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

            _ads_var = _path + "." + _fields.get(AdsValveKeys.VAR)
            _device_class = _int_to_valve_device_class(_device_type)

            _entities.append(
                AdsValve(
                    ads_hub=_ads_hub,
                    ads_var=_ads_var,
                    name=_name,
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

    ads_var = config[AdsValveKeys.VAR]
    name = config[AdsValveKeys.NAME]
    device_class = config.get(AdsValveKeys.DEVICE_CLASS)

    add_entities(
        [
            AdsValve(
                ads_hub=ads_hub,
                ads_var=ads_var,
                name=name,
                device_class=device_class,
            )
        ]
    )


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
        self._attr_is_closed = True

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, pyads.PLCTYPE_BOOL)

    def open_valve(self, **kwargs) -> None:
        """Open the valve."""
        self._ads_hub.write_by_name(self._ads_var, True, pyads.PLCTYPE_BOOL)
        self._attr_is_closed = False

    def close_valve(self, **kwargs) -> None:
        """Close the valve."""
        self._ads_hub.write_by_name(self._ads_var, False, pyads.PLCTYPE_BOOL)
        self._attr_is_closed = True
