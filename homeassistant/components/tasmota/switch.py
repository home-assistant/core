"""Support for Tasmota switches."""
import logging

from homeassistant.components import switch
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN as TASMOTA_DOMAIN
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW, clear_discovery_hash
from .mixins import TasmotaAvailability, TasmotaDiscoveryUpdate

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Tasmota switch dynamically through discovery."""

    async def async_discover(entity, discovery_hash):
        """Discover and add a Tasmota switch."""
        try:
            await _async_setup_entity(
                entity, discovery_hash, async_add_entities, config_entry
            )
        except Exception:
            clear_discovery_hash(hass, discovery_hash)
            raise

    async_dispatcher_connect(
        hass,
        TASMOTA_DISCOVERY_ENTITY_NEW.format(switch.DOMAIN, TASMOTA_DOMAIN),
        async_discover,
    )


async def _async_setup_entity(entity, discovery_hash, async_add_entities, config_entry):
    """Set up the Tasmota switch."""
    async_add_entities([TasmotaSwitch(entity, discovery_hash, config_entry)])


class TasmotaSwitch(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    SwitchEntity,
    RestoreEntity,
):
    """Representation of a Tasmota switch."""

    def __init__(self, entity, discovery_hash, config_entry):
        """Initialize the Tasmota switch."""
        self._state = False
        self._sub_state = None

        self._entity = entity
        self._entity.set_on_state_callback(self.state_updated)
        self._unique_id = entity.unique_id

        TasmotaAvailability.__init__(self, entity)
        TasmotaDiscoveryUpdate.__init__(
            self, entity, discovery_hash, self.discovery_update
        )

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def discovery_update(self, update):
        """Handle updated discovery message."""
        self._entity.config_update(update)
        await self._subscribe_topics()
        self.async_write_ha_state()

    @callback
    def state_updated(self, state):
        """Handle new MQTT state messages."""
        self._state = state
        self.async_write_ha_state()

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await self._entity.subscribe_topics()

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        await self._entity.unsubscribe_topics()
        await TasmotaAvailability.async_will_remove_from_hass(self)
        await TasmotaDiscoveryUpdate.async_will_remove_from_hass(self)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._entity.name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return False

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._entity.unique_id

    @property
    def icon(self):
        """Return the icon."""
        return None

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {"identifiers": {(TASMOTA_DOMAIN, self._entity.device_id)}}

    async def async_turn_on(self, **kwargs):
        """Turn the device on.

        This method is a coroutine.
        """
        self._entity.set_state(True)

    async def async_turn_off(self, **kwargs):
        """Turn the device off.

        This method is a coroutine.
        """
        self._entity.set_state(False)
