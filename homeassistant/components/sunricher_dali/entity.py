"""Base entity for Sunricher DALI integration."""

import logging
from typing import override

from PySrDaliGateway import CallbackEventType, DaliGateway, DaliObjectBase, Device

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


class DaliCenterEntity(Entity):
    """Base entity for DALI Center objects (devices, scenes, etc.)."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, dali_object: DaliObjectBase, gateway: DaliGateway) -> None:
        """Initialize base entity."""
        self._dali_object = dali_object
        self._gateway = gateway
        self._attr_unique_id = dali_object.unique_id
        self._unavailable_logged = False
        self._attr_available = True

    @override
    async def async_added_to_hass(self) -> None:
        """Register availability listener."""
        self.async_on_remove(
            self._dali_object.register_listener(
                CallbackEventType.ONLINE_STATUS,
                self._handle_availability,
            )
        )

    def _ensure_gateway_connected(self) -> None:
        """Raise if a command can't reach the gateway."""
        # The library drops commands silently when the gateway is disconnected.
        if not self._gateway.is_connected:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="gateway_not_connected",
            )

    @callback
    def _handle_availability(self, available: bool) -> None:
        """Handle availability changes."""
        if not available and not self._unavailable_logged:
            _LOGGER.info("Entity %s became unavailable", self.entity_id)
            self._unavailable_logged = True
        elif available and self._unavailable_logged:
            _LOGGER.info("Entity %s is back online", self.entity_id)
            self._unavailable_logged = False

        self._attr_available = available
        self.schedule_update_ha_state()


class DaliDeviceEntity(DaliCenterEntity):
    """Base entity for DALI Device objects."""

    def __init__(
        self, hass: HomeAssistant, device: Device, entry: DaliCenterConfigEntry
    ) -> None:
        """Initialize device entity."""
        super().__init__(device, entry.runtime_data.gateway)
        self._device = device
        self._attr_available = device.status == "online"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.dev_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.model,
            via_device_id=dr.async_get_device_id_by_identifier(
                hass, (DOMAIN, device.gw_sn), config_entry_id=entry.entry_id
            ),
        )
