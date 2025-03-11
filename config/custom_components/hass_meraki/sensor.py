"""The Sensor Component."""

import logging

import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
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

        entities.append(MerakiStatusSensor(coordinator, serial))

        if device_data.get("productType") not in ["switch", "wireless", "appliance"]:
            continue
        entities.append(MerakiClientSensor(coordinator, serial))
    async_add_entities(entities)


class MerakiClientSensor(CoordinatorEntity, Entity):
    """Sensor to track active clients for a Meraki device."""

    def __init__(self, coordinator, serial) -> None:  # noqa: D107
        super().__init__(coordinator)
        self._serial = serial
        # Gib der Entität nur den „reinen“ Namen
        self._attr_name = "Clients"  # oder "Status", "Temperatur", etc.
        self._attr_unique_id = f"{serial}_clients"
        self._attr_unit_of_measurement = ""
        self._attr_state_class = "measurement"
        self._attr_has_entity_name = True

        device_data = coordinator.data.get(serial, {})
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
    def state(self):
        """Return the number of active clients."""
        return self.coordinator.data.get(self._serial, {}).get("client_count", 0)


class MerakiStatusSensor(CoordinatorEntity, Entity):
    """Sensor to track device status for a Meraki device."""

    def __init__(self, coordinator, serial) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._serial = serial
        # Setze den Entitätsnamen nur als "Status" (ohne Gerätebezeichnung, da diese
        # im Device Registry hinterlegt wird)
        self._attr_name = "Status"
        self._attr_unique_id = f"{serial}_state"
        # Kein state_class, da es sich nicht um einen numerischen Messwert handelt
        self._attr_has_entity_name = True

        device_data = coordinator.data.get(serial, {})
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "name": device_data.get("name", f"Meraki Device {serial}"),
            "manufacturer": "Cisco Meraki",
            "model": device_data.get("model", "Unknown"),
            "sw_version": device_data.get("firmware", "Unknown"),
            "connections": {("mac", device_data.get("mac", "Unknown"))},
        }

    @property
    def state(self):
        """Return the status of the device."""
        return self.coordinator.data.get(self._serial, {}).get("state", "Unknown")

    @property
    def icon(self):
        """Return the appropriate mdi icon based on the status."""
        status = self.state.lower()
        if status == "online":
            return "mdi:ethernet"
        if status in ["offline", "dormant"]:
            return "mdi:ethernet-off"
        if status == "alerting":
            return "mdi:alert"
        return "mdi:help-circle"
