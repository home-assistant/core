"""Axis network device abstraction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import axis

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import ATTR_MANUFACTURER, DOMAIN as AXIS_DOMAIN
from .config import AxisConfig
from .entity_loader import AxisEntityLoader
from .event_source import AxisEventSource

if TYPE_CHECKING:
    from .. import AxisConfigEntry


class AxisHub:
    """Manages a Axis device."""

    def __init__(
        self, hass: HomeAssistant, config_entry: AxisConfigEntry, api: axis.AxisDevice
    ) -> None:
        """Initialize the device."""
        self.hass = hass
        self.config = AxisConfig.from_config_entry(config_entry)
        self.entity_loader = AxisEntityLoader(self)
        self.event_source = AxisEventSource(hass, config_entry, api)
        self.api = api

        self.fw_version = api.vapix.firmware_version
        self.product_type = api.vapix.product_type
        self.unique_id = format_mac(api.vapix.serial_number)

        self.additional_diagnostics: dict[str, Any] = {}

    @property
    def available(self) -> bool:
        """Connection state to the device."""
        return self.event_source.available

    # Signals

    @property
    def signal_reachable(self) -> str:
        """Device specific event to signal a change in connection status."""
        return self.event_source.signal_reachable

    @property
    def signal_new_address(self) -> str:
        """Device specific event to signal a change in device address."""
        return f"axis_new_address_{self.config.entry.entry_id}"

    @staticmethod
    async def async_new_address_callback(
        hass: HomeAssistant, config_entry: AxisConfigEntry
    ) -> None:
        """Handle signals of device getting new address.

        Called when config entry is updated.
        This is a static method because a class method (bound method),
        cannot be used with weak references.
        """
        hub = config_entry.runtime_data
        hub.config = AxisConfig.from_config_entry(config_entry)
        hub.event_source.config_entry = config_entry
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
        self.event_source.setup()

    async def shutdown(self, event: Event) -> None:
        """Stop the event stream."""
        self.event_source.teardown()

    @callback
    def teardown(self) -> None:
        """Reset this device to default state."""
        self.event_source.teardown()
