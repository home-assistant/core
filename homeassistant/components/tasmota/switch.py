"""Support for Tasmota switches."""
import logging

from homeassistant.components import switch
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
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

    def __init__(self, tasmota_entity, **kwds):
        """Initialize the Tasmota switch."""
        self._state = False
        self._sub_state = None

        self._unique_id = tasmota_entity.unique_id

        super().__init__(
            discovery_update=self.discovery_update,
            tasmota_entity=tasmota_entity,
            **kwds,
        )

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()
        self._tasmota_entity.set_on_state_callback(self.state_updated)
        await self._subscribe_topics()

    async def discovery_update(self, update):
        """Handle updated discovery message."""
        self._tasmota_entity.config_update(update)
        await self._subscribe_topics()
        self.async_write_ha_state()

    @callback
    def state_updated(self, state):
        """Handle new MQTT state messages."""
        self._state = state
        self.async_write_ha_state()

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await self._tasmota_entity.subscribe_topics()

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        await self._tasmota_entity.unsubscribe_topics()
        await super().async_will_remove_from_hass()

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._tasmota_entity.name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._tasmota_entity.unique_id

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {"connections": {(CONNECTION_NETWORK_MAC, self._tasmota_entity.mac)}}

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self._tasmota_entity.set_state(True)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        self._tasmota_entity.set_state(False)
