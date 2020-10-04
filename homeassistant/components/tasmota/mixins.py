"""Tasnmota entity mixins."""
import logging

from homeassistant.components.mqtt.const import MQTT_CONNECTED, MQTT_DISCONNECTED
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .discovery import (
    TASMOTA_DISCOVERY_ENTITY_UPDATED, clear_discovery_hash, set_discovery_hash
)

DATA_MQTT = "mqtt"

_LOGGER = logging.getLogger(__name__)


class TasmotaEntity(Entity):
    """Base class for Tasmota entities."""

    def __init__(self, tasmota_entity) -> None:
        """Initialize."""
        self._tasmota_entity = tasmota_entity


class TasmotaAvailability(TasmotaEntity):
    """Mixin used for platforms that report availability."""

    def __init__(self, **kwds) -> None:
        """Initialize the availability mixin."""
        self._available = False
        super().__init__(**kwds)

    async def async_added_to_hass(self) -> None:
        """Subscribe MQTT events."""
        await super().async_added_to_hass()
        self._tasmota_entity.set_on_availability_callback(self.availability_updated)
        self.async_on_remove(
            async_dispatcher_connect(self.hass, MQTT_CONNECTED, self.async_mqtt_connect)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, MQTT_DISCONNECTED, self.async_mqtt_connect
            )
        )

    async def availability_discovery_update(self, config: dict) -> None:
        """Handle updated discovery message."""

    @callback
    def availability_updated(self, available: bool) -> None:
        """Handle updated availability."""
        self._available = available
        self.async_write_ha_state()

    @callback
    def async_mqtt_connect(self):
        """Update state on connection/disconnection to MQTT broker."""
        if not self.hass.is_stopping:
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        if not self.hass.data[DATA_MQTT].connected and not self.hass.is_stopping:
            return False
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
        await super().async_added_to_hass()
        self._removed_from_hass = False

        @callback
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

    async def async_will_remove_from_hass(self) -> None:
        """Stop listening to signal and cleanup discovery data.."""
        self._cleanup_discovery_on_remove()

    def _cleanup_discovery_on_remove(self) -> None:
        """Stop listening to signal and cleanup discovery data."""
        if not self._removed_from_hass:
            clear_discovery_hash(self.hass, self._discovery_hash)
            self._removed_from_hass = True
