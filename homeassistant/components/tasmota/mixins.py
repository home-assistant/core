"""Tasmota entity mixins."""
import logging

from homeassistant.components.mqtt import (
    async_subscribe_connection_status,
    is_connected as mqtt_connected,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .discovery import (
    TASMOTA_DISCOVERY_ENTITY_UPDATED,
    clear_discovery_hash,
    set_discovery_hash,
)

_LOGGER = logging.getLogger(__name__)


class TasmotaEntity(Entity):
    """Base class for Tasmota entities."""

    def __init__(self, tasmota_entity) -> None:
        """Initialize."""
        self._state = None
        self._tasmota_entity = tasmota_entity
        self._unique_id = tasmota_entity.unique_id

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        self._tasmota_entity.set_on_state_callback(self.state_updated)
        await self._subscribe_topics()

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        await self._tasmota_entity.unsubscribe_topics()
        await super().async_will_remove_from_hass()

    async def discovery_update(self, update, write_state=True):
        """Handle updated discovery message."""
        self._tasmota_entity.config_update(update)
        await self._subscribe_topics()
        if write_state:
            self.async_write_ha_state()

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await self._tasmota_entity.subscribe_topics()

    @callback
    def state_updated(self, state, **kwargs):
        """Handle state updates."""
        self._state = state
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {"connections": {(CONNECTION_NETWORK_MAC, self._tasmota_entity.mac)}}

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._tasmota_entity.name

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id


class TasmotaAvailability(TasmotaEntity):
    """Mixin used for platforms that report availability."""

    def __init__(self, **kwds) -> None:
        """Initialize the availability mixin."""
        self._available = False
        super().__init__(**kwds)

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""
        self._tasmota_entity.set_on_availability_callback(self.availability_updated)
        self.async_on_remove(
            async_subscribe_connection_status(self.hass, self.async_mqtt_connected)
        )
        await super().async_added_to_hass()

    @callback
    def availability_updated(self, available: bool) -> None:
        """Handle updated availability."""
        if available and not self._available:
            self._tasmota_entity.poll_status()
        self._available = available
        self.async_write_ha_state()

    @callback
    def async_mqtt_connected(self, _):
        """Update state on connection/disconnection to MQTT broker."""
        if not self.hass.is_stopping:
            if not mqtt_connected(self.hass):
                self._available = False
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._available


class TasmotaDiscoveryUpdate(TasmotaEntity):
    """Mixin used to handle updated discovery message."""

    def __init__(self, discovery_hash, discovery_update, **kwds) -> None:
        """Initialize the discovery update mixin."""
        self._discovery_hash = discovery_hash
        self._discovery_update = discovery_update
        self._removed_from_hass = False
        super().__init__(**kwds)

    async def async_added_to_hass(self) -> None:
        """Subscribe to discovery updates."""
        self._removed_from_hass = False
        await super().async_added_to_hass()

        async def discovery_callback(config):
            """Handle discovery update."""
            _LOGGER.debug(
                "Got update for entity with hash: %s '%s'",
                self._discovery_hash,
                config,
            )
            if not self._tasmota_entity.config_same(config):
                # Changed payload: Notify component
                _LOGGER.debug("Updating component: %s", self.entity_id)
                await self._discovery_update(config)
            else:
                # Unchanged payload: Ignore to avoid changing states
                _LOGGER.debug("Ignoring unchanged update for: %s", self.entity_id)

        # Set in case the entity has been removed and is re-added, for example when changing entity_id
        set_discovery_hash(self.hass, self._discovery_hash)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                TASMOTA_DISCOVERY_ENTITY_UPDATED.format(*self._discovery_hash),
                discovery_callback,
            )
        )

    @callback
    def add_to_platform_abort(self) -> None:
        """Abort adding an entity to a platform."""
        clear_discovery_hash(self.hass, self._discovery_hash)
        super().add_to_platform_abort()

    async def async_will_remove_from_hass(self) -> None:
        """Stop listening to signal and cleanup discovery data.."""
        if not self._removed_from_hass:
            clear_discovery_hash(self.hass, self._discovery_hash)
            self._removed_from_hass = True
        await super().async_will_remove_from_hass()
