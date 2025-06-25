"""Tasmota entity mixins."""

from __future__ import annotations

import logging
from typing import Any

from hatasmota.entity import (
    TasmotaAvailability as HATasmotaAvailability,
    TasmotaEntity as HATasmotaEntity,
    TasmotaEntityConfig,
)
from hatasmota.models import DiscoveryHashType

from homeassistant.components.mqtt import (
    async_subscribe_connection_status,
    is_connected as mqtt_connected,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
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

    _attr_has_entity_name = True

    def __init__(self, tasmota_entity: HATasmotaEntity) -> None:
        """Initialize."""
        self._tasmota_entity = tasmota_entity
        self._unique_id = tasmota_entity.unique_id
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, tasmota_entity.mac)}
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""
        await self._subscribe_topics()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe when removed."""
        await self._tasmota_entity.unsubscribe_topics()
        await super().async_will_remove_from_hass()

    async def discovery_update(
        self, update: TasmotaEntityConfig, write_state: bool = True
    ) -> None:
        """Handle updated discovery message."""
        self._tasmota_entity.config_update(update)
        await self._subscribe_topics()
        if write_state:
            self.async_write_ha_state()

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await self._tasmota_entity.subscribe_topics()

    @property
    def name(self) -> str | None:
        """Return the name of the binary sensor."""
        return self._tasmota_entity.name

    @property
    def should_poll(self) -> bool:
        """Return the polling state."""
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id


class TasmotaOnOffEntity(TasmotaEntity):
    """Base class for Tasmota entities which can be on or off."""

    def __init__(self, **kwds: Any) -> None:
        """Initialize."""
        self._on_off_state: bool = False
        super().__init__(**kwds)

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""
        self._tasmota_entity.set_on_state_callback(self.state_updated)
        await super().async_added_to_hass()

    @callback
    def state_updated(self, state: bool, **kwargs: Any) -> None:
        """Handle state updates."""
        self._on_off_state = state
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._on_off_state


class TasmotaAvailability(TasmotaEntity):
    """Mixin used for platforms that report availability."""

    _tasmota_entity: HATasmotaAvailability

    def __init__(self, **kwds: Any) -> None:
        """Initialize the availability mixin."""
        super().__init__(**kwds)
        if self._tasmota_entity.deep_sleep_enabled:
            self._available = True
        else:
            self._available = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""
        self._tasmota_entity.set_on_availability_callback(self.availability_updated)
        self.async_on_remove(
            async_subscribe_connection_status(self.hass, self.async_mqtt_connected)
        )
        await super().async_added_to_hass()
        if self._tasmota_entity.deep_sleep_enabled:
            await self._tasmota_entity.poll_status()

    async def availability_updated(self, available: bool) -> None:
        """Handle updated availability."""
        await self._tasmota_entity.poll_status()
        self._available = available
        self.async_write_ha_state()

    @callback
    def async_mqtt_connected(self, _: bool) -> None:
        """Update state on connection/disconnection to MQTT broker."""
        if not self.hass.is_stopping:
            if not mqtt_connected(self.hass):
                self._available = False
            elif self._tasmota_entity.deep_sleep_enabled:
                self._available = True
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._available


class TasmotaDiscoveryUpdate(TasmotaEntity):
    """Mixin used to handle updated discovery message."""

    def __init__(self, discovery_hash: DiscoveryHashType, **kwds: Any) -> None:
        """Initialize the discovery update mixin."""
        self._discovery_hash = discovery_hash
        self._removed_from_hass = False
        super().__init__(**kwds)

    async def async_added_to_hass(self) -> None:
        """Subscribe to discovery updates."""
        self._removed_from_hass = False
        await super().async_added_to_hass()

        @callback
        def discovery_callback(config: TasmotaEntityConfig) -> None:
            """Handle discovery update.

            If the config has changed we will create a task to
            do the discovery update.

            As this callback can fire when nothing has changed, this
            is a normal function to avoid task creation until it is needed.
            """
            _LOGGER.debug(
                "Got update for entity with hash: %s '%s'",
                self._discovery_hash,
                config,
            )
            if not self._tasmota_entity.config_same(config):
                # Changed payload: Notify component
                _LOGGER.debug("Updating component: %s", self.entity_id)
                self.hass.async_create_task(self.discovery_update(config))
            else:
                # Unchanged payload: Ignore to avoid changing states
                _LOGGER.debug("Ignoring unchanged update for: %s", self.entity_id)

        # Set in case the entity has been removed and is re-added,
        # for example when changing entity_id
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
