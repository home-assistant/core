"""Lytiva switches via MQTT (live updates + HA compatible + group support)."""
from __future__ import annotations
import logging
import json
from typing import Any, Dict

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------
#  REGISTER DISCOVERY CALLBACK
# ---------------------------------------------------------
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    register_cb = data.get("register_switch_callback")

    if register_cb:
        register_cb(lambda payload: _handle_discovery(hass, entry, payload, async_add_entities))
        _LOGGER.debug("Lytiva Switch: discovery callback registered.")


# ---------------------------------------------------------
#  DISCOVERY HANDLER
# ---------------------------------------------------------
def _handle_discovery(hass, entry, payload, async_add_entities):
    try:
        uid = payload.get("unique_id") or payload.get("address")
        if uid is None:
            return

        uid = str(uid)

        # FIX: If address missing, use unique_id
        if "address" not in payload or payload.get("address") is None:
            payload["address"] = uid

        store = hass.data[DOMAIN][entry.entry_id]
        by_uid = store["entities_by_unique_id"]
        by_addr = store["entities_by_address"]

        # Duplicate check
        if uid in by_uid:
            return
        if str(payload["address"]) in by_addr:
            return

        ent = LytivaSwitch(hass, entry, payload)
        by_uid[uid] = ent
        by_addr[str(ent.address)] = ent

        # Register MQTT live update
        mqtt = store.get("mqtt_client")
        if mqtt:
            topic = payload.get("status_topic")
            if topic:
                mqtt.subscribe(topic, lambda msg: hass.add_job(ent._update_from_payload, msg))

        hass.add_job(async_add_entities, [ent])

    except Exception as e:
        _LOGGER.exception("Lytiva Switch discovery failed: %s", e)


# ---------------------------------------------------------
#  SWITCH ENTITY
# ---------------------------------------------------------
class LytivaSwitch(SwitchEntity):
    """Representation of a Lytiva Switch."""

    def __init__(self, hass, entry, cfg):
        self.hass = hass
        self._entry = entry
        self._cfg = cfg or {}

        # Identity
        self._attr_name = cfg.get("name", "Lytiva Switch")
        self._attr_unique_id = str(cfg.get("unique_id") or cfg.get("address"))

        # Address
        addr = cfg.get("address") or self._attr_unique_id
        try:
            self.address = int(addr)
        except Exception:
            self.address = addr

        self.command_topic = cfg.get("command_topic")
        self._attr_is_on = False

    # ---------------------------------------------------------
    #  DEVICE INFO (area support)
    # ---------------------------------------------------------
    @property
    def device_info(self):
        dev = self._cfg.get("device")

        # If no device provided → DO NOT create a device entry
        if not dev:
            return None

        identifiers = dev.get("identifiers")
        if isinstance(identifiers, list) and identifiers:
            identifiers = {(DOMAIN, identifiers[0])}
        else:
            identifiers = {(DOMAIN, self._attr_unique_id)}

        info = {
            "identifiers": identifiers,
            "name": dev.get("name", self._attr_name),
            "manufacturer": dev.get("manufacturer", "Lytiva"),
            "model": dev.get("model", "Switch"),
        }

        if dev.get("suggested_area"):
            info["suggested_area"] = dev["suggested_area"]

        return info

    # ---------------------------------------------------------
    #  MQTT PUBLISH
    # ---------------------------------------------------------
    def _publish(self, payload):
        try:
            mqtt = self.hass.data[DOMAIN][self._entry.entry_id]["mqtt_client"]
            mqtt.publish(self.command_topic, json.dumps(payload))
        except Exception as e:
            _LOGGER.error("Switch MQTT publish error: %s", e)

    # ---------------------------------------------------------
    #  TURN ON / OFF
    # ---------------------------------------------------------
    async def async_turn_on(self, **kwargs):
        payload = json.loads(self._cfg.get("payload_on") or {"address":54058,"type":"switch","power":true,"version":"v1.0"})
        self._attr_is_on = True
        self._publish(payload)
        self.async_write_ha_state()


    async def async_turn_off(self, **kwargs):
        payload = json.loads(self._cfg.get("payload_off") or {"address":54058,"type":"switch","power":false,"version":"v1.0"})
        self._attr_is_on = False
        self._publish(payload)
        self.async_write_ha_state()


    # ---------------------------------------------------------
    #  UPDATE FROM DEVICE PAYLOAD
    # ---------------------------------------------------------
    async def _update_from_payload(self, payload):
        """Update switch state from device MQTT payload."""
        try:
            if payload.get("address") != self.address:
                return

            # Extract state from nested "switch" object
            sw = payload.get("switch", {})
            power = sw.get("power")
            if power is not None:
                self._attr_is_on = bool(power)

            self.async_write_ha_state()

        except Exception as e:
            _LOGGER.exception("Switch update error: %s", e)