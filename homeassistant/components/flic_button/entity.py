"""Base entity for Flic Button integration."""

from __future__ import annotations

import logging

from pyflic_ble import FlicState

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

from . import FlicButtonData
from .const import DEVICE_TYPE_MODEL_NAMES, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FlicButtonEntity(Entity):
    """Base entity for Flic Button integration."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _unavailable_logged: bool = False

    def __init__(self, data: FlicButtonData) -> None:
        """Initialize the Flic button entity."""
        client = data.client
        serial = data.serial_number
        model_name = DEVICE_TYPE_MODEL_NAMES[client.device_type]

        if serial:
            device_name = f"{model_name} ({serial})"
        else:
            device_name = f"Flic {client.address[-5:]}"

        fw = client.state.firmware_version
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client.address)},
            connections={(CONNECTION_BLUETOOTH, client.address)},
            name=device_name,
            manufacturer="Shortcut Labs",
            model=model_name,
            serial_number=serial,
            sw_version=str(fw) if fw is not None else None,
        )
        self._client = client

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.state.connected

    async def async_added_to_hass(self) -> None:
        """Register state callback when entity is added."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._client.register_state_callback(self._handle_state_update)
        )

    @callback
    def _handle_state_update(self, state: FlicState) -> None:
        """Handle state updates from the client."""
        is_available = state.connected

        if not is_available and not self._unavailable_logged:
            _LOGGER.info("%s is unavailable", self._client.address)
            self._unavailable_logged = True
        elif is_available and self._unavailable_logged:
            _LOGGER.info("%s is back online", self._client.address)
            self._unavailable_logged = False

        self.async_write_ha_state()
