"""Support for Tasmota switches."""
import logging

from homeassistant.components import switch
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN as TASMOTA_DOMAIN
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .mixins import TasmotaAvailability, TasmotaDiscoveryUpdate

_LOGGER = logging.getLogger(__name__)


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

    async_dispatcher_connect(
        hass,
        TASMOTA_DISCOVERY_ENTITY_NEW.format(switch.DOMAIN, TASMOTA_DOMAIN),
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
            discovery_update=self.discovery_update,
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
