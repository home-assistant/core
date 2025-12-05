"""Lytiva IR AC Climate via MQTT - integrated with central MQTT handler (discovery + live STATUS)."""
from __future__ import annotations
import logging
import json

from jinja2 import Template

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from typing import Any, Dict

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

HVAC_MAP = {
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "dry": HVACMode.DRY,
    "fan_only": HVACMode.FAN_ONLY,
    "auto": HVACMode.AUTO,
}
REVERSE_HVAC = {v: k for k, v in HVAC_MAP.items()}


def _parse_template(template_str: str | None, msg_payload: Any) -> str | None:
    """Parse Jinja2 template with payload."""
    if not template_str:
        return None
    try:
        try:
            payload_json = json.loads(msg_payload)
        except Exception:
            payload_json = {}
        t = Template(template_str)
        result = t.render(
            value_json=payload_json,
            value=msg_payload.decode() if isinstance(msg_payload, (bytes, bytearray)) else msg_payload,
        )
        return result.strip()
    except Exception as e:
        _LOGGER.error("Template render error: %s | Template: %s", e, template_str)
        return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up climate entities dynamically from MQTT discovery and register for live updates."""
    integration = hass.data[DOMAIN][entry.entry_id]
    by_uid: Dict[str, Any] = integration["entities_by_unique_id"]
    by_addr: Dict[str, Any] = integration["entities_by_address"]

    def add_new_climate(payload: dict):
        """Add newly discovered climate device (and register it for STATUS lookups)."""
        try:
            uid = payload.get("unique_id") or payload.get("address")
            if uid is None:
                _LOGGER.debug("Climate discovery missing unique_id/address: %s", payload)
                return
            uid = str(uid)

            # Duplicate protection
            if uid in by_uid:
                _LOGGER.debug("Climate already exists (uid=%s) - updating payload", uid)
                ent = by_uid[uid]
                try:
                    ent.payload = payload
                    ent._cfg = payload  # keep consistent with older code expecting _cfg
                except Exception:
                    pass
                return

            # Create entity
            ent = LytivaClimateEntity(hass, entry, payload, integration)

            # register lookups by uid and address so central STATUS handler can find it
            by_uid[uid] = ent
            addr = payload.get("address") or uid
            by_addr[str(addr)] = ent

            async_add_entities([ent], True)
            _LOGGER.info("✅ Lytiva climate added: %s (uid=%s address=%s)", payload.get("name"), uid, addr)

        except Exception as e:
            _LOGGER.exception("Error adding climate device: %s", e)

    register = integration.get("register_climate_callback")
    if register:
        register(add_new_climate)

class LytivaClimateEntity(ClimateEntity, RestoreEntity):
    """Representation of IR AC (Air Conditioner) managed via central STATUS."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, payload: dict, integration: dict):
        self.hass = hass
        self.entry = entry
        self.payload = payload
        self._integration = integration
        self._cfg = payload  # keep name consistent with other entities

        self._name = payload.get("name", "Lytiva Climate")
        self._unique_id = str(payload.get("unique_id") or payload.get("address") or f"lytiva_climate_{id(payload)}")
        self._address = payload.get("address")

        # Command topics and templates (from discovery)
        self._topic_mode_cmd = payload.get("mode_command_topic")
        self._topic_temp_cmd = payload.get("temperature_command_topic")
        self._topic_fan_mode_cmd = payload.get("fan_mode_command_topic")
        self._topic_preset_cmd = payload.get("preset_mode_command_topic")

        self._mode_command_template = payload.get("mode_command_template")
        self._temp_command_template = payload.get("temperature_command_template")
        self._fan_mode_command_template = payload.get("fan_mode_command_template")
        self._preset_mode_command_template = payload.get("preset_mode_command_template")

        # State templates (kept for compatibility; live updates come from STATUS)
        self._mode_state_template = payload.get("mode_state_template")
        self._target_temp_template = payload.get("target_temperature_template")
        self._current_temp_template = payload.get("current_temperature_template")
        self._fan_mode_state_template = payload.get("fan_mode_state_template")
        self._preset_mode_state_template = payload.get("preset_mode_state_template")

        # Supported values
        modes = payload.get("modes", ["cool", "heat", "dry", "fan_only", "auto"])
        self._hvac_modes = [HVAC_MAP.get(m) for m in modes if m in HVAC_MAP]

        self._fan_modes = payload.get("fan_modes", ["Vlow", "Low", "Med", "High", "Top", "Auto"])
        self._preset_modes = payload.get("preset_modes", ["On", "Off"])

        # Device info
        dev_meta = payload.get("device", {}) or {}
        self._manufacturer = dev_meta.get("manufacturer", "Lytiva")
        self._model = dev_meta.get("model", "IR AC")
        self._area = dev_meta.get("suggested_area")

        # State defaults
        self._available = True
        self._target_temp = float(payload.get("min_temp", 24))
        self._current_temp = None
        self._fan_mode = self._fan_modes[0] if self._fan_modes else None
        self._hvac_mode = self._hvac_modes[0] if self._hvac_modes else HVACMode.COOL
        self._preset = "On"

        # Temperature limits
        self._min_temp = payload.get("min_temp", 16)
        self._max_temp = payload.get("max_temp", 30)
        self._temp_step = payload.get("temp_step", 1)

        _LOGGER.info("Initialized LytivaClimateEntity: %s (uid=%s address=%s)", self._name, self._unique_id, self._address)

    # -----------------------------
    # Central STATUS update
    # -----------------------------
    async def _update_from_payload(self, payload: dict):
        """Update climate state from central STATUS payload with unit handling."""
        try:
            # verify address matches
            if self._address is not None:
                if str(payload.get("address")) != str(self._address):
                    return

            ir_ac = payload.get("ir_ac") or payload.get("ir") or {}
            updated = False

            # hvac mode
            mode = ir_ac.get("mode")
            if mode:
                if mode == "fan":
                    mode = "fan_only"
                if mode in HVAC_MAP:
                    new_mode = HVAC_MAP[mode]
                    if new_mode != self._hvac_mode:
                        self._hvac_mode = new_mode
                        updated = True

            # target temperature
            if "temperature" in ir_ac:
                try:
                    t = float(ir_ac.get("temperature"))
                    t = round(t, 1)  # no conversion, assume Celsius
                    if t != self._target_temp:
                        self._target_temp = t
                        updated = True
                except Exception:
                    pass

            # current temperature
            if "current_temperature" in ir_ac:
                try:
                    ct = float(ir_ac.get("current_temperature"))
                    ct = round(ct, 1)  # no conversion, assume Celsius
                    if ct != self._current_temp:
                        self._current_temp = ct
                        updated = True
                except Exception:
                    pass

            # fan speed mapping
            if "fan_speed" in ir_ac:
                try:
                    fan_speed = int(ir_ac.get("fan_speed", 0))
                    mapping = {0: self._fan_modes[0] if self._fan_modes else None,
                            1: "Vlow", 2: "Low", 3: "Med", 4: "High", 5: "Top", 6: "Auto"}
                    new_fan_mode = mapping.get(fan_speed, self._fan_modes[0] if self._fan_modes else None)
                    if new_fan_mode != self._fan_mode:
                        self._fan_mode = new_fan_mode
                        updated = True
                except Exception:
                    pass

            # preset/power
            if "power" in ir_ac:
                p = bool(ir_ac.get("power"))
                new_preset = "On" if p else "Off"
                if new_preset != self._preset:
                    self._preset = new_preset
                    updated = True

            if updated:
                self._available = True
                try:
                    self.async_write_ha_state()
                except Exception:
                    self.schedule_update_ha_state()

        except Exception as e:
            _LOGGER.exception("Climate update error for %s: %s", self._name, e)

    # -----------------------------
    # properties
    # -----------------------------
    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

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
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self.payload.get("device", {}).get("name", self._name),
            "manufacturer": self._manufacturer,
            "model": self._model,
        }
        if self._area:
            info["suggested_area"] = self._area
        return info

    @property
    def available(self):
        return self._available

    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS

    @property
    def hvac_modes(self):
        return self._hvac_modes

    @property
    def hvac_mode(self):
        return self._hvac_mode

    @property
    def fan_modes(self):
        return self._fan_modes

    @property
    def fan_mode(self):
        return self._fan_mode

    @property
    def preset_modes(self):
        return self._preset_modes

    @property
    def preset_mode(self):
        return self._preset

    @property
    def current_temperature(self):
        return self._current_temp

    @property
    def target_temperature(self):
        return self._target_temp

    @property
    def min_temp(self):
        return self._min_temp

    @property
    def max_temp(self):
        return self._max_temp

    @property
    def target_temperature_step(self):
        return self._temp_step

    @property
    def supported_features(self):
        features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        if self._fan_modes:
            features |= ClimateEntityFeature.FAN_MODE
        return features

    @property
    def extra_state_attributes(self):
        return {
            "preset_mode": self._preset,
            "fan_mode": self._fan_mode,
        }

    # -----------------------------
    # control methods (use discovery templates/topics)
    # -----------------------------
    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        """Send HVAC mode command via MQTT using the configured template/topic."""
        if not self._mode_command_template or not self._topic_mode_cmd:
            _LOGGER.error("No mode command configured for climate %s", self._name)
            return

        mode_str = REVERSE_HVAC.get(hvac_mode)
        if not mode_str:
            _LOGGER.error("Unknown HVAC mode requested: %s", hvac_mode)
            return
        try:
            payload = Template(self._mode_command_template).render(value=mode_str, mapping=REVERSE_HVAC)
            self._integration["mqtt_client"].publish(self._topic_mode_cmd, payload)
            self._hvac_mode = hvac_mode
            self.schedule_update_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to publish HVAC mode command: %s", e, exc_info=True)

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get("temperature")
        if temp is None or not self._temp_command_template or not self._topic_temp_cmd:
            _LOGGER.error("Missing temperature or command config for %s", self._name)
            return
        try:
            temp = max(self._min_temp, min(self._max_temp, float(temp)))
            payload = Template(self._temp_command_template).render(value=int(temp))
            self._integration["mqtt_client"].publish(self._topic_temp_cmd, payload)
            self._target_temp = temp
            self.schedule_update_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to publish temperature command: %s", e, exc_info=True)

    async def async_set_fan_mode(self, fan_mode: str):
        if not self._fan_mode_command_template or not self._topic_fan_mode_cmd:
            _LOGGER.error("No fan mode command configured for %s", self._name)
            return
        if fan_mode not in self._fan_modes:
            _LOGGER.error("Invalid fan mode: %s for %s", fan_mode, self._name)
            return
        try:
            payload = Template(self._fan_mode_command_template).render(
                value=fan_mode,
                mapping={fm: i + 1 for i, fm in enumerate(self._fan_modes)}
            )
            self._integration["mqtt_client"].publish(self._topic_fan_mode_cmd, payload)
            self._fan_mode = fan_mode
            self.schedule_update_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to publish fan mode command: %s", e, exc_info=True)

    async def async_set_preset_mode(self, preset_mode: str):
        if not self._preset_mode_command_template or not self._topic_preset_cmd:
            _LOGGER.error("No preset command configured for %s", self._name)
            return
        if preset_mode not in self._preset_modes:
            _LOGGER.error("Invalid preset requested: %s", preset_mode)
            return
        try:
            payload = Template(self._preset_mode_command_template).render(value=preset_mode)
            self._integration["mqtt_client"].publish(self._topic_preset_cmd, payload)
            self._preset = preset_mode
            self.schedule_update_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to publish preset command: %s", e, exc_info=True)

    async def async_added_to_hass(self):
        """Restore previous state when added to hass."""
        await super().async_added_to_hass()
        old_state = await self.async_get_last_state()
        if old_state is not None:
            _LOGGER.info("Restoring previous state for %s", self._name)
            try:
                if old_state.state in [mode.value for mode in HVACMode]:
                    self._hvac_mode = HVACMode(old_state.state)
            except Exception:
                pass
            if old_state.attributes.get("temperature"):
                try:
                    self._target_temp = float(old_state.attributes["temperature"])
                except Exception:
                    pass
            if old_state.attributes.get("fan_mode"):
                self._fan_mode = old_state.attributes.get("fan_mode")
            if old_state.attributes.get("preset_mode"):
                self._preset = old_state.attributes.get("preset_mode")
            _LOGGER.info("Previous state restored for %s", self._name)
