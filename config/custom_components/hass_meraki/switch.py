"""The switch Component for Meraki PoE control."""

import logging
from functools import partial

import meraki

from homeassistant.components.switch import SwitchEntity
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Meraki PoE switches via config entry."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    device_registry = dr.async_get(hass)
    # config_entry is stored in hass.data[DOMAIN] in __init__.py
    entry = hass.data[DOMAIN].get("config_entry")
    if not entry:
        _LOGGER.error("Config entry not found!")
        return

    entities = []
    # Create switches for each device that has active PoE ports
    for serial, device_data in coordinator.data.items():
        # Register the device in the Device Registry
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, serial)},
            manufacturer="Cisco Meraki",
            name=device_data.get("name", f"Meraki Device {serial}"),
            model=device_data.get("model", "Unknown"),
            sw_version=device_data.get("firmware", "Unknown"),
            connections={("mac", device_data.get("mac", "Unknown"))},
        )

        if device_data.get("active_poe_ports"):
            # Assume active_poe_ports is a list of dict objects
            for port in device_data.get("active_poe_ports"):
                entities.append(MerakiPoeSwitch(coordinator, serial, port))
    async_add_entities(entities)

    # Subscribe to a dispatcher signal to dynamically add new PoE ports when discovered.
    # Your coordinator update method must send this signal when new ports appear.
    def _handle_new_entity(new_entity):
        # Schedule the addition of the entity on the event loop thread-safely.
        hass.loop.call_soon_threadsafe(lambda: async_add_entities([new_entity]))

    async_dispatcher_connect(
        hass,
        f"{DOMAIN}_new_poe_port",
        _handle_new_entity,
    )


class MerakiPoeSwitch(CoordinatorEntity, RestoreEntity, SwitchEntity):
    """Representation of a Meraki PoE switch for a specific port."""

    def __init__(self, coordinator, serial, port):
        """Initialize the switch entity for a specific port."""
        # device_data for the device this port belongs to
        device_data = coordinator.data.get(serial, {})
        super().__init__(coordinator)
        self._serial = serial
        self._port = port  # Expecting port to be a dict with port details

        # Set a name using available port details
        if isinstance(port, dict):
            port_number = port.get("port", "Unknown")
            system_name = port.get("systemName")
            if system_name:
                self._attr_name = f"Port {port_number} {system_name}"
            else:
                self._attr_name = f"Port {port_number}"
        else:
            self._attr_name = f"Port {port}"

        self._attr_unique_id = (
            f"{serial}_poe_port_{port.get('port') if isinstance(port, dict) else port}"
        )
        self._attr_has_entity_name = True
        # Default to True; will be updated via API calls.
        self._poe_enabled = True

        # Device registry info so the entity is linked with the device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "name": device_data.get("name", f"Meraki Device {serial}"),
            "manufacturer": "Cisco Meraki",
            "model": device_data.get("model", "Unknown"),
            "sw_version": device_data.get("firmware", "Unknown"),
            "connections": {("mac", device_data.get("mac", "Unknown"))},
        }

    async def async_added_to_hass(self):
        """Restore state when added to hass and update if needed."""
        await super().async_added_to_hass()
        # Restore last known state if available.
        last_state = await self.async_get_last_state()
        if last_state is not None:
            # Restore PoE state: assume state is "on" if enabled, otherwise "off"
            self._poe_enabled = last_state.state == "on"
        self.async_write_ha_state()

    @property
    def is_on(self):
        """Return True if PoE is enabled on this port."""
        return self._poe_enabled

    async def async_turn_on(self, **kwargs):
        """Enable PoE power on this port."""
        result = await self.hass.async_add_executor_job(self._set_poe, True)
        if result:
            self._poe_enabled = result.get("poeEnabled", True)
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Disable PoE power on this port."""
        result = await self.hass.async_add_executor_job(self._set_poe, False)
        if result:
            self._poe_enabled = result.get("poeEnabled", False)
            self.async_write_ha_state()

    def _set_poe(self, enable):
        """Call the Meraki API to change the PoE state for this port."""
        # Retrieve API key from the config entry stored in the coordinator.
        api_key = self.coordinator.config_entry.data["api_key"]
        dashboard = meraki.DashboardAPI(api_key=api_key, suppress_logging=True)
        try:
            # Use the appropriate API call; here, we assume the port identifier is under "port" if self._port is a dict.
            port_identifier = (
                self._port.get("port") if isinstance(self._port, dict) else self._port
            )
            response = dashboard.switch.updateDeviceSwitchPort(
                self._serial, port_identifier, poeEnabled=enable
            )
            return response
        except meraki.APIError as err:
            _LOGGER.error(
                "Failed to set PoE state on port %s: %s", port_identifier, err
            )
            return False
