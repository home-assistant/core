"""The switch Component."""

import logging

import meraki

from homeassistant.components.switch import SwitchEntity
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Meraki sensors via config entry."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    device_registry = dr.async_get(hass)
    config_entry = hass.data[DOMAIN].get("config_entry")
    if not config_entry:
        _LOGGER.error("Config entry not found!")
        return

    entities = []
    # Erstelle Sensoren für Geräte, die Client-Daten unterstützen (z. B. Switch, Access Point, Appliance)
    for serial, device_data in coordinator.data.items():
        # Registriere das Gerät im Device Registry
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, serial)},
            manufacturer="Cisco Meraki",
            name=device_data.get("name", f"Meraki Device {serial}"),
            model=device_data.get("model", "Unknown"),
            sw_version=device_data.get("firmware", "Unknown"),
            connections={("mac", device_data.get("mac", "Unknown"))},
        )

        if device_data.get("active_poe_ports"):
            for port in device_data.get("active_poe_ports"):
                entities.append(MerakiPoeSwitch(coordinator, serial, port))  # noqa: PERF401
    async_add_entities(entities)

    # Optionally, subscribe to updates to add or remove entities dynamically.
    # Dynamic entity management can be more involved—this is a simplified approach.


class MerakiPoeSwitch(CoordinatorEntity, SwitchEntity):  # noqa: D101
    def __init__(self, coordinator, serial, port):
        """Initialize the switch entity for a specific port."""
        device_data = coordinator.data.get(serial, {})
        super().__init__(coordinator)
        self._serial = serial
        if "systemName" in device_data["active_poe_ports"][port]:
            self._attr_name = (
                f"Port {port} {device_data['active_poe_ports'][port]['systemName']}"
            )
        else:
            self._attr_name = f"Port {port}"
        self._attr_unique_id = f"{serial}_poe_port_{port}"
        self._attr_has_entity_name = True
        self._port = port
        self._poe_enabled = True

        # Gerätedaten, damit die Entität dem Gerät zugeordnet wird
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "name": device_data.get("name", f"Meraki Device {serial}"),
            "manufacturer": "Cisco Meraki",
            "model": device_data.get("model", "Unknown"),
            "sw_version": device_data.get("firmware", "Unknown"),
            "connections": {("mac", device_data.get("mac", "Unknown"))},
        }

    @property
    def is_on(self):
        """Return True if PoE is enabled on this port."""
        # Assume the API returns a boolean 'poeEnabled' flag
        return self._poe_enabled
        # return True

    async def async_turn_on(self, **kwargs):
        """Enable PoE power on this port."""
        result = await self.hass.async_add_executor_job(self._set_poe, True)
        if result:
            self._poe_enabled = result.get("poeEnabled")
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Disable PoE power on this port."""
        result = await self.hass.async_add_executor_job(self._set_poe, False)
        if result:
            self._poe_enabled = result.get("poeEnabled")
            self.async_write_ha_state()

    def _set_poe(self, enable):
        """Call the Meraki API to change the PoE state for this port."""
        # Adjust the API call to match your needs. This is an example.

        api_key = self.coordinator.config_entry.data["api_key"]
        dashboard = meraki.DashboardAPI(api_key=api_key, suppress_logging=True)
        try:
            # This is a placeholder; replace with the actual API method and parameters.
            response = dashboard.switch.updateDeviceSwitchPort(
                self._serial, self._port, poeEnabled=enable
            )
            return response
        except meraki.APIError as err:
            _LOGGER.error("Failed to set PoE state on port %s: %s", self._port, err)
            return False

    # @property
    # def extra_state_attributes(self):
    #     """Optional: expose additional port info as attributes."""
    #     return {"port_name": self._port.get("name")}
