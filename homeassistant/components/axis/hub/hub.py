"""Axis network device abstraction."""

from __future__ import annotations

from typing import Any

import axis

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import ATTR_MANUFACTURER, DOMAIN as AXIS_DOMAIN
from .config import AxisConfig
from .connectivity import AxisConnectivity
from .entity_loader import AxisEntityLoader


class AxisHub:
    """Manages a Axis device."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: axis.AxisDevice
    ) -> None:
        """Initialize the device."""
        self.hass = hass
        self.config = AxisConfig.from_config_entry(config_entry)
        self.entity_loader = AxisEntityLoader(self)
        self.connectivity = AxisConnectivity(hass, config_entry, api)
        self.api = api

        self.fw_version = api.vapix.firmware_version
        self.product_type = api.vapix.product_type
        self.unique_id = format_mac(api.vapix.serial_number)

        self.additional_diagnostics: dict[str, Any] = {}

    @callback
    @staticmethod
    def get_hub(hass: HomeAssistant, config_entry: ConfigEntry) -> AxisHub:
        """Get Axis hub from config entry."""
        hub: AxisHub = hass.data[AXIS_DOMAIN][config_entry.entry_id]
        return hub

    @property
    def available(self) -> bool:
        """Connection state to the device."""
        return self.connectivity.available

    # Signals

    @property
    def signal_reachable(self) -> str:
        """Device specific event to signal a change in connection status."""
        return self.connectivity.signal_reachable

    @property
    def signal_new_address(self) -> str:
        """Device specific event to signal a change in device address."""
        return f"axis_new_address_{self.config.entry.entry_id}"

    @staticmethod
    async def async_new_address_callback(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Handle signals of device getting new address.

        Called when config entry is updated.
        This is a static method because a class method (bound method),
        cannot be used with weak references.
        """
        hub = AxisHub.get_hub(hass, config_entry)
        hub.config = AxisConfig.from_config_entry(config_entry)
        hub.connectivity.config_entry = config_entry
        hub.api.config.host = hub.config.host
        async_dispatcher_send(hass, hub.signal_new_address)

    async def async_update_device_registry(self) -> None:
        """Update device registry."""
        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config.entry.entry_id,
            configuration_url=self.api.config.url,
            connections={(CONNECTION_NETWORK_MAC, self.unique_id)},
            identifiers={(AXIS_DOMAIN, self.unique_id)},
            manufacturer=ATTR_MANUFACTURER,
            model=f"{self.config.model} {self.product_type}",
            name=self.config.name,
            sw_version=self.fw_version,
        )

    # Setup and teardown methods

    @callback
    def setup(self) -> None:
        """Set up the device events."""
        self.entity_loader.initialize_platforms()
        self.connectivity.setup()

    async def shutdown(self, event: Event) -> None:
        """Stop the event stream."""
        self.connectivity.teardown()

    @callback
    def teardown(self) -> None:
        """Reset this device to default state."""
        self.connectivity.teardown()
