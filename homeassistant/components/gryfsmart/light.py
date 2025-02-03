"""Handle the Gryf Smart light platform functionality."""

import logging

from pygryfsmart.device import _GryfDevice, _GryfOutput

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_API, CONF_DEVICES, CONF_ID, CONF_NAME, DOMAIN
from .entity import _GryfSmartEntityBase

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Set up the Light platform."""
    lights = []

    for conf in hass.data[DOMAIN].get("lights", {}):
        device = _GryfOutput(
            conf.get(CONF_NAME),
            conf.get(CONF_ID) // 10,
            conf.get(CONF_ID) % 10,
            hass.data[DOMAIN]["api"],
        )
        lights.append(GryfLight(device, hass))

    async_add_entities(lights)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Config flow for Light platform."""
    lights = []
    light_config = config_entry.data[CONF_DEVICES]

    for conf in light_config:
        if conf.get(CONF_TYPE) == Platform.LIGHT:
            device = _GryfOutput(
                conf.get(CONF_NAME),
                conf.get(CONF_ID) // 10,
                conf.get(CONF_ID) % 10,
                hass.data[DOMAIN][CONF_API],
            )
            lights.append(GryfLight(device, hass))

    async_add_entities(lights)


class GryfLightBase(LightEntity):
    """Gryf Smart light base."""

    _is_on = False
    _device: _GryfDevice
    _hass: HomeAssistant

    async def update(self, state):
        """Update state function."""
        self._is_on = state
        self.async_write_ha_state()

    def __init__(self) -> None:
        """Initialize Gryf Smart Light base."""
        self._device.subscribe(self.update)

    @property
    def is_on(self):
        """Return state."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn light on."""
        await self._device.turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn light off."""
        await self._device.turn_off()

    async def async_added_to_hass(self) -> None:
        """Add to hass."""
        await super().async_added_to_hass()

    async def async_removed_from_hass(self) -> None:
        """Remove from hass."""
        await super().async_will_remove_from_hass()


class GryfLight(_GryfSmartEntityBase, GryfLightBase):
    """Gryf Smart Light class."""

    def __init__(
        self,
        device: _GryfDevice,
        hass: HomeAssistant,
    ) -> None:
        """Init the Gryf Light."""
        self._device = device
        self._hass = hass
        GryfLightBase.__init__(self)
        _GryfSmartEntityBase.__init__(self)
