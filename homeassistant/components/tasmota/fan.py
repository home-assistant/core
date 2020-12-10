"""Support for Tasmota fans."""

from hatasmota import const as tasmota_const

from homeassistant.components import fan
from homeassistant.components.fan import FanEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .mixins import TasmotaAvailability, TasmotaDiscoveryUpdate

HA_TO_TASMOTA_SPEED_MAP = {
    fan.SPEED_OFF: tasmota_const.FAN_SPEED_OFF,
    fan.SPEED_LOW: tasmota_const.FAN_SPEED_LOW,
    fan.SPEED_MEDIUM: tasmota_const.FAN_SPEED_MEDIUM,
    fan.SPEED_HIGH: tasmota_const.FAN_SPEED_HIGH,
}

TASMOTA_TO_HA_SPEED_MAP = {v: k for k, v in HA_TO_TASMOTA_SPEED_MAP.items()}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Tasmota fan dynamically through discovery."""

    @callback
    def async_discover(tasmota_entity, discovery_hash):
        """Discover and add a Tasmota fan."""
        async_add_entities(
            [TasmotaFan(tasmota_entity=tasmota_entity, discovery_hash=discovery_hash)]
        )

    hass.data[
        DATA_REMOVE_DISCOVER_COMPONENT.format(fan.DOMAIN)
    ] = async_dispatcher_connect(
        hass,
        TASMOTA_DISCOVERY_ENTITY_NEW.format(fan.DOMAIN),
        async_discover,
    )


class TasmotaFan(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    FanEntity,
):
    """Representation of a Tasmota fan."""

    def __init__(self, **kwds):
        """Initialize the Tasmota fan."""
        self._state = None

        super().__init__(
            **kwds,
        )

    @property
    def speed(self):
        """Return the current speed."""
        return TASMOTA_TO_HA_SPEED_MAP.get(self._state)

    @property
    def speed_list(self):
        """Get the list of available speeds."""
        return list(HA_TO_TASMOTA_SPEED_MAP)

    @property
    def supported_features(self):
        """Flag supported features."""
        return fan.SUPPORT_SET_SPEED

    async def async_set_speed(self, speed):
        """Set the speed of the fan."""
        if speed not in HA_TO_TASMOTA_SPEED_MAP:
            raise ValueError(f"Unsupported speed {speed}")
        if speed == fan.SPEED_OFF:
            await self.async_turn_off()
        else:
            self._tasmota_entity.set_speed(HA_TO_TASMOTA_SPEED_MAP[speed])

    async def async_turn_on(self, speed=None, **kwargs):
        """Turn the fan on."""
        # Tasmota does not support turning a fan on with implicit speed
        await self.async_set_speed(speed or fan.SPEED_MEDIUM)

    async def async_turn_off(self, **kwargs):
        """Turn the fan off."""
        self._tasmota_entity.set_speed(tasmota_const.FAN_SPEED_OFF)
