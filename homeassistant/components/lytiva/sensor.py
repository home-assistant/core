"""Lytiva sensors via MQTT with live updates via central STATUS handler (generic)."""
from __future__ import annotations
import logging
import json
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_ICONS = {
    "temperature": "mdi:thermometer",
    "humidity": "mdi:water-percent",
    "co2": "mdi:molecule-co2",
    "illuminance": "mdi:brightness-5",
    "lux_levels": "mdi:brightness-5",
    "default": "mdi:circle-outline",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Lytiva sensors."""
    store = hass.data[DOMAIN][entry.entry_id]
    by_uid = store["entities_by_unique_id"]
    by_addr = store["entities_by_address"]

    # register callback
    async def _sensor_discovery(payload: dict):
        uid = str(payload.get("unique_id") or payload.get("address"))
        if uid in by_uid:
            return

        sensor = LytivaSensor(hass, entry.entry_id, payload)
        by_uid[uid] = sensor
        by_addr[str(sensor.address)] = sensor

        hass.add_job(async_add_entities, [sensor])
        _LOGGER.info("Discovered Lytiva sensor: %s", sensor.name)

    store.setdefault("sensor_callbacks", []).append(lambda payload: hass.async_create_task(_sensor_discovery(payload)))

class LytivaSensor(SensorEntity):
    """MQTT Sensor with live updates via central STATUS (generic)."""

    def __init__(self, hass: HomeAssistant, entry_id: str, cfg: dict):
        self.hass = hass
        self._entry_id = entry_id
        self._cfg = cfg
        self._state = None
        self._attributes: dict = {}

        # Name & ID
        self._attr_name = cfg.get("name", "Lytiva Sensor")
        self._attr_unique_id = str(cfg.get("unique_id") or cfg.get("address"))

        # Address
        try:
            self.address = int(cfg.get("address") or self._attr_unique_id)
        except Exception:
            self.address = self._attr_unique_id

        self._device_class = cfg.get("device_class")
        self._unit_of_measurement = cfg.get("unit_of_measurement")
        self._icon = cfg.get("icon") or DEFAULT_ICONS.get(self._device_class, DEFAULT_ICONS["default"])

        device_info = cfg.get("device", {})
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(device_info.get("identifiers", [self._attr_unique_id])[0]))},
            "name": device_info.get("name", self._attr_name),
            "manufacturer": device_info.get("manufacturer", "Lytiva"),
            "model": device_info.get("model", "Sensor"),
            "suggested_area": device_info.get("suggested_area", "Unknown"),
        }

    @property
    def icon(self):
        return self._icon

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_unit_of_measurement(self):
        return self._unit_of_measurement

    @property
    def device_class(self):
        return self._device_class

    async def _update_from_payload(self, payload: dict):
        """Update sensor state from shared STATUS topic (generic)."""
        try:
            if str(payload.get("address")) != str(self.address):
                return

            # find the sensor subkey automatically (exclude standard keys)
            standard_keys = {"version", "message", "type", "address"}
            sensor_keys = [k for k in payload.keys() if k not in standard_keys]

            if not sensor_keys:
                return

            sensor_data = payload.get(sensor_keys[0], {})  # e.g., "temperature_humidity_sensor", "co2_sensor", "lux_sensor"

            # state: pick first numeric key as main state
            numeric_keys = [k for k, v in sensor_data.items() if isinstance(v, (int, float))]
            self._state = sensor_data.get(numeric_keys[0]) if numeric_keys else None

            # attributes: all other keys
            self._attributes = {k: v for k, v in sensor_data.items() if k != numeric_keys[0]} if numeric_keys else sensor_data

            self.async_write_ha_state()

        except Exception as e:
            _LOGGER.exception("Sensor update failed: %s", e)
