"""Lytiva curtain (cover) via MQTT - mirror of light.py style (discovery, address/uid handling,
device_info with suggested_area, duplicate protection, centralized MQTT publish & status updates).
"""
from __future__ import annotations
import logging
import json
from typing import Any, Dict, Optional

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


# -----------------------------
#  PLATFORM SETUP (Discovery)
# -----------------------------
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    register_cb = data.get("register_cover_callback")

    if register_cb:
        register_cb(lambda payload: _handle_discovery(hass, entry, payload, async_add_entities))
        _LOGGER.debug("Lytiva Cover: discovery callback registered.")
    else:
        _LOGGER.warning("Lytiva Cover: register_cover_callback NOT found.")


# -----------------------------
#  DISCOVERY HANDLER
# -----------------------------
def _handle_discovery(hass: HomeAssistant, entry: ConfigEntry, payload: Dict[str, Any], async_add_entities):
    try:
        uid = payload.get("unique_id") or payload.get("address")
        if uid is None:
            _LOGGER.debug("Lytiva Cover discovery payload missing unique id/address: %s", payload)
            return

        uid = str(uid)

        # If discovery payload didn't include address, use unique_id as address (fallback)
        if "address" not in payload or payload.get("address") in (None, ""):
            payload["address"] = uid

        store = hass.data[DOMAIN][entry.entry_id]
        by_uid: Dict[str, Any] = store["entities_by_unique_id"]
        by_addr: Dict[str, Any] = store["entities_by_address"]

        # If already present by unique id -> update config (avoid duplicates)
        if uid in by_uid:
            ent = by_uid[uid]
            try:
                ent._cfg = payload
            except Exception:
                pass
            _LOGGER.debug("Lytiva Cover discovery: existing entity updated uid=%s", uid)
            return

        # If address already present -> avoid creating duplicates
        addr_str = str(payload.get("address"))
        if addr_str in by_addr:
            ent = by_addr[addr_str]
            try:
                # Map the uid -> existing entity so future lookups by unique_id work
                by_uid[uid] = ent
                ent._cfg = payload
            except Exception:
                pass
            _LOGGER.debug("Lytiva Cover discovery: existing entity found by address=%s", addr_str)
            return

        # create new entity
        ent = LytivaCurtain(hass, entry, payload)
        by_uid[uid] = ent
        by_addr[str(ent.address)] = ent

        hass.add_job(async_add_entities, [ent])
        _LOGGER.info("Lytiva Cover added: %s (uid=%s address=%s)", ent.name, uid, ent.address)

    except Exception as e:
        _LOGGER.exception("Lytiva Cover discovery error: %s", e)


# -----------------------------
#  COVER ENTITY
# -----------------------------
class LytivaCurtain(CoverEntity):
    """Representation of a Lytiva Curtain device."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, cfg: Dict[str, Any]) -> None:
        self.hass = hass
        self._entry = entry
        self._cfg: Dict[str, Any] = cfg or {}

        # identity
        self._attr_name = self._cfg.get("name", "Lytiva Curtain")
        self._attr_unique_id = str(self._cfg.get("unique_id") or self._cfg.get("address"))

        # address (prefer int if it's integer-like)
        addr = self._cfg.get("address")
        try:
            # some discovery send numeric addresses; enforce int when possible
            self.address = int(addr)
        except Exception:
            self.address = str(addr)

        # topics / payloads from discovery
        self._command_topic: Optional[str] = self._cfg.get("command_topic")
        self._state_topic: Optional[str] = self._cfg.get("state_topic")
        self._position_topic: Optional[str] = self._cfg.get("position_topic") or self._state_topic
        self._set_position_template: Optional[str] = self._cfg.get("set_position_template")
        self._payload_open: Optional[Any] = self._cfg.get("payload_open")
        self._payload_close: Optional[Any] = self._cfg.get("payload_close")
        self._payload_stop: Optional[Any] = self._cfg.get("payload_stop")

        # runtime state
        self._position: Optional[int] = None
        self._attr_available = True

        # device metadata
        dev_meta = self._cfg.get("device", {}) or {}
        self._manufacturer = dev_meta.get("manufacturer", "Lytiva")
        self._model = dev_meta.get("model", "Curtain")
        self._area = dev_meta.get("suggested_area")
        self._sw_version = dev_meta.get("sw_version")
        self._hw_version = dev_meta.get("hw_version")

        _LOGGER.debug(
            "Initialized LytivaCurtain name=%s uid=%s address=%s state_topic=%s set_position_template=%s",
            self._attr_name, self._attr_unique_id, self.address, self._state_topic, bool(self._set_position_template),
        )

    # -----------------------------
    #  DEVICE INFO (area + identifiers)
    # -----------------------------
    @property
    def device_info(self):
        dev = self._cfg.get("device")

        # If no device provided → DO NOT create a device entry
        if not dev:
            return None

        identifiers = dev.get("identifiers")
        if isinstance(identifiers, (list, tuple)) and identifiers:
            identifiers = {(DOMAIN, identifiers[0])}
        else:
            identifiers = {(DOMAIN, self._attr_unique_id)}

        info = {
            "identifiers": identifiers,
            "name": dev.get("name", self._attr_name),
            "manufacturer": dev.get("manufacturer", self._manufacturer),
            "model": dev.get("model", self._model),
        }
        if self._sw_version:
            info["sw_version"] = self._sw_version
        if self._hw_version:
            info["hw_version"] = self._hw_version
        if self._area:
            info["suggested_area"] = self._area
        return info

    # -----------------------------
    #  BASIC PROPS
    # -----------------------------
    @property
    def name(self) -> str:
        return self._attr_name

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def current_cover_position(self) -> Optional[int]:
        return self._position

    @property
    def is_closed(self) -> Optional[bool]:
        if self._position is None:
            return None
        return self._position == 0

    # -----------------------------
    #  MQTT PUBLISH HELPER
    # -----------------------------
    def _publish_payload(self, payload: Dict[str, Any]) -> None:
        try:
            # ensure address present in payload (device expects it)
            if self.address is not None:
                try:
                    payload["address"] = int(self.address)
                except Exception:
                    payload["address"] = self.address
            mqtt = self.hass.data[DOMAIN][self._entry.entry_id]["mqtt_client"]
            topic = self._command_topic or f"LYT/{self.address}/CMD"
            mqtt.publish(topic, json.dumps(payload))
        except Exception as e:
            _LOGGER.exception("Lytiva Cover publish failed for %s: %s", self._attr_name, e)

    # -----------------------------
    #  COMMANDS (open/close/stop/set_position)
    # -----------------------------
    def open_cover(self, **_):
        try:
            if self._payload_open and self._command_topic:
                # payload already a JSON string or dict in discovery; normalize to dict
                payload = _ensure_dict(self._payload_open)
                self._publish_payload(payload)
                _LOGGER.debug("Published open for %s -> %s", self._attr_name, self._command_topic)
        except Exception as e:
            _LOGGER.exception("open_cover error for %s: %s", self._attr_name, e)

    def close_cover(self, **_):
        try:
            if self._payload_close and self._command_topic:
                payload = _ensure_dict(self._payload_close)
                self._publish_payload(payload)
                _LOGGER.debug("Published close for %s -> %s", self._attr_name, self._command_topic)
        except Exception as e:
            _LOGGER.exception("close_cover error for %s: %s", self._attr_name, e)

    def stop_cover(self, **_):
        try:
            if self._payload_stop and self._command_topic:
                payload = _ensure_dict(self._payload_stop)
                self._publish_payload(payload)
                _LOGGER.debug("Published stop for %s -> %s", self._attr_name, self._command_topic)
        except Exception as e:
            _LOGGER.exception("stop_cover error for %s: %s", self._attr_name, e)

    def set_cover_position(self, **kwargs):
        try:
            pos = kwargs.get("position")
            if pos is None:
                return

            # if discovery provided a template, use it (expects "{{ position }}")
            template = self._set_position_template or self._cfg.get("set_position_template") or ""
            if template:
                try:
                    # replace placeholder with an integer position
                    payload_text = template.replace("{{ position }}", str(int(pos)))
                    # try parse dict, otherwise send raw text
                    try:
                        payload = json.loads(payload_text)
                        self._publish_payload(payload)
                    except Exception:
                        mqtt = self.hass.data[DOMAIN][self._entry.entry_id]["mqtt_client"]
                        topic = self._command_topic or f"LYT/{self.address}/CMD"
                        mqtt.publish(topic, payload_text)
                    _LOGGER.debug("Published set_position for %s -> %s", self._attr_name, payload_text)
                    return
                except Exception:
                    _LOGGER.exception("Error applying set_position_template for %s", self._attr_name)

            # fallback: build a simple curtain payload with curtain_level
            payload = {"version": "v1.0", "type": "curtain", "address": self.address, "curtain_level": int(pos)}
            self._publish_payload(payload)
            _LOGGER.debug("Published fallback set_position for %s -> %s", self._attr_name, payload)
        except Exception as e:
            _LOGGER.exception("set_cover_position error for %s: %s", self._attr_name, e)

    # -----------------------------
    #  CENTRAL STATUS UPDATE (called from __init__.py handler)
    # -----------------------------
    async def _update_from_payload(self, payload: Dict[str, Any]) -> None:
        try:
            # match by address (address may be int or string)
            inc = payload.get("address") or payload.get("unique_id")
            if inc is None:
                return
            try:
                if str(inc) != str(self.address):
                    return
            except Exception:
                return

            # look for nested curtain.curtain_level or top-level curtain_level/position/level
            level = None
            if isinstance(payload.get("curtain"), dict):
                level = payload["curtain"].get("curtain_level")
            if level is None:
                level = payload.get("curtain_level") or payload.get("position") or payload.get("level")

            if level is not None:
                try:
                    new_pos = int(level)
                except Exception:
                    return
                if new_pos != self._position:
                    self._position = new_pos
                    _LOGGER.debug("Curtain %s updated position -> %s", self._attr_name, self._position)
                    try:
                        self.async_write_ha_state()
                    except Exception:
                        # fallback scheduling
                        try:
                            self.schedule_update_ha_state()
                        except Exception:
                            pass
        except Exception as e:
            _LOGGER.exception("Lytiva Cover update error for %s: %s", self._attr_name, e)


# -----------------------------
#  HELPERS
# -----------------------------
def _ensure_dict(val: Any) -> Dict[str, Any]:
    """Normalize payload that may be a JSON string or dict into a dict."""
    if isinstance(val, dict):
        return val
    try:
        if isinstance(val, str):
            return json.loads(val)
    except Exception:
        pass
    # last resort: return a dict-wrapped message
    return {"payload": val}
