"""Lytiva Binary Sensors via central STATUS handler (generic, live updates)."""
from __future__ import annotations
import logging
import json
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_ICONS = {
    "motion": "mdi:motion-sensor",
    "occupancy": "mdi:account-multiple",
    "parking": "mdi:car",
    "default": "mdi:circle-outline",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Lytiva binary sensors via discovery callbacks."""
    store = hass.data[DOMAIN][entry.entry_id]
    by_uid = store["entities_by_unique_id"]
    by_addr = store["entities_by_address"]

    async def add_binary_sensor(payload: dict):
        uid = str(payload.get("unique_id") or payload.get("address"))
        if uid in by_uid:
            return

        sensor = LytivaBinarySensor(hass, entry.entry_id, payload)
        by_uid[uid] = sensor
        by_addr[str(sensor.address)] = sensor

        async_add_entities([sensor])
        _LOGGER.info("Discovered Lytiva binary sensor: %s", sensor.name)

    # register callback
    store.setdefault("binary_sensor_callbacks", []).append(lambda payload: hass.async_create_task(add_binary_sensor(payload)))

class LytivaBinarySensor(BinarySensorEntity):
    """Generic binary sensor with live updates via central STATUS topic."""

    def __init__(self, hass: HomeAssistant, entry_id: str, cfg: dict):
        self.hass = hass
        self._entry_id = entry_id
        self._cfg = cfg
        self._state = None
        self._attributes = {}

        # Name & ID
        self._attr_name = cfg.get("name", "Lytiva Binary Sensor")
        self._attr_unique_id = str(cfg.get("unique_id") or cfg.get("address"))

        # Address
        try:
            self.address = int(cfg.get("address") or self._attr_unique_id)
        except Exception:
            self.address = self._attr_unique_id

        self._device_class = cfg.get("device_class")
        self._payload_on = cfg.get("payload_on", "ON")
        self._payload_off = cfg.get("payload_off", "OFF")
        self._value_template = cfg.get("value_template")
        self._icon = cfg.get("icon") or DEFAULT_ICONS.get(self._device_class, DEFAULT_ICONS["default"])

        device_info = cfg.get("device", {})
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(device_info.get("identifiers", [self._attr_unique_id])[0]))},
            "name": device_info.get("name", self._attr_name),
            "manufacturer": device_info.get("manufacturer", "Lytiva"),
            "model": device_info.get("model", "Binary Sensor"),
            "suggested_area": device_info.get("suggested_area", "Unknown"),
        }

    @property
    def icon(self):
        return self._icon

    @property
    def is_on(self):
        return self._state

    @property
    def device_class(self):
        return self._device_class
    
    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        return self._attributes

    async def _update_from_payload(self, payload: dict):
        """Update binary sensor state from STATUS payload (generic)."""
        try:
            if str(payload.get("address")) != str(self.address):
                return

            # Auto-detect relevant sensor key
            standard_keys = {"version", "message", "type", "address"}
            sensor_keys = [k for k in payload.keys() if k not in standard_keys]
            if not sensor_keys:
                return

            sensor_data = payload.get(sensor_keys[0], {})

            # Evaluate template if provided
            value = None
            if self._value_template:
                template = Template(self._value_template, self.hass)
                value = template.async_render({"value_json": payload}).strip().lower()
            else:
                # Fallback: check for boolean-like fields automatically
                for v in sensor_data.values():
                    if isinstance(v, bool):
                        value = str(v).lower()
                        break
                    if isinstance(v, (int, float)):
                        value = "true" if v else "false"
                        break

            if value is not None:
                self._state = value == str(self._payload_on).lower()

            for k, v in sensor_data.items():
                if k not in ("occupancy", "motion", "parking", "state"):
                    self._attributes[k] = v

                self.async_write_ha_state()

        except Exception as e:
            _LOGGER.exception("Binary sensor update failed: %s", e)
