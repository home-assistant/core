"""Support for ADS switch platform."""

from __future__ import annotations

from typing import Any

import pyads
import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchDeviceClass,
    SwitchEntity,
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
    AdsDiscoveryKeys,
    AdsSwitchKeys,
)
from .entity import AdsEntity

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_HUB, default=CONF_ADS_HUB_DEFAULT): cv.string,
        vol.Required(AdsSwitchKeys.VAR): cv.string,
        vol.Optional(AdsSwitchKeys.NAME, default=AdsSwitchKeys.DEFAULT_NAME): cv.string,
        vol.Optional(AdsSwitchKeys.DEVICE_CLASS): cv.string,
    }
)


def _int_to_switch_device_class(value: int) -> SwitchDeviceClass | None:
    """Map integer values to SwitchDeviceClass enums."""
    mapping = {
        0: None,
        1: SwitchDeviceClass.SWITCH,
        2: SwitchDeviceClass.OUTLET,
    }
    return mapping.get(value)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the switch platform for ADS."""

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

            _ads_var = _path + "." + _fields.get(AdsSwitchKeys.VAR)
            _device_class = _int_to_switch_device_class(_device_type)

            _entities.append(
                AdsSwitch(
                    ads_hub=_ads_hub,
                    name=_name,
                    ads_var=_ads_var,
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

    ads_var: str = config[AdsSwitchKeys.VAR]
    name: str = config[AdsSwitchKeys.NAME]
    device_class: str | None = config.get(AdsSwitchKeys.DEVICE_CLASS)

    add_entities(
        [
            AdsSwitch(
                ads_hub=ads_hub,
                name=name,
                ads_var=ads_var,
                device_class=device_class,
            )
        ]
    )


class AdsSwitch(AdsEntity, SwitchEntity):
    """Representation of an ADS switch device."""

    def __init__(
        self, ads_hub, name: str, ads_var: str, device_class: str | None
    ) -> None:
        """Initialize AdsSwitch entity."""
        super().__init__(ads_hub, name, ads_var)
        if device_class is not None:
            try:
                self._attr_device_class = SwitchDeviceClass(device_class)
            except ValueError:
                self._attr_device_class = None
        else:
            self._attr_device_class = None

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        if self._ads_var is not None:
            await self.async_initialize_device(
                self._ads_var, pyads.PLCTYPE_BOOL, STATE_KEY_STATE
            )

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return self._state_dict[STATE_KEY_STATE]

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._ads_hub.write_by_name(self._ads_var, True, pyads.PLCTYPE_BOOL)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._ads_hub.write_by_name(self._ads_var, False, pyads.PLCTYPE_BOOL)
