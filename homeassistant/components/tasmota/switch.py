"""Support for Tasmota switches."""

from homeassistant.components import switch
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .mixins import TasmotaAvailability, TasmotaDiscoveryUpdate


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Tasmota switch dynamically through discovery."""

    @callback
    def async_discover(tasmota_entity, discovery_hash):
        """Discover and add a Tasmota switch."""
        async_add_entities(
            [
                TasmotaSwitch(
                    tasmota_entity=tasmota_entity, discovery_hash=discovery_hash
                )
            ]
        )

    hass.data[
        DATA_REMOVE_DISCOVER_COMPONENT.format(switch.DOMAIN)
    ] = async_dispatcher_connect(
        hass,
        TASMOTA_DISCOVERY_ENTITY_NEW.format(switch.DOMAIN),
        async_discover,
    )


class TasmotaSwitch(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    SwitchEntity,
):
    """Representation of a Tasmota switch."""

    def __init__(self, **kwds):
        """Initialize the Tasmota switch."""
        self._state = False

        super().__init__(
            **kwds,
        )

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self._tasmota_entity.set_state(True)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        self._tasmota_entity.set_state(False)
