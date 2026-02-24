"""Climate entities for MyNeomitis integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MyNeomitisConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORTED_MODELS: frozenset[str] = frozenset({"EV30", "ECTRL", "ESTAT", "RSS-ECTRL"})
SUPPORTED_SUB_MODELS: frozenset[str] = frozenset({"NTD", "ETRV"})

PRESET_MODE_MAP = {
    "comfort": 1,
    "eco": 2,
    "antifrost": 3,
    "standby": 4,
    "boost": 6,
    "setpoint": 8,
    "comfort_plus": 20,
    "auto": 60,
}
REVERSE_PRESET_MODE_MAP = {v: k for k, v in PRESET_MODE_MAP.items()}

PRESET_MODE_MODELES = {
    "EV30": ["setpoint", "boost", "eco", "comfort", "auto", "antifrost", "standby"],
    "ECTRL": [
        "setpoint",
        "boost",
        "eco",
        "comfort",
        "comfort_plus",
        "auto",
        "antifrost",
        "standby",
    ],
    "ESTAT": [
        "setpoint",
        "boost",
        "eco",
        "comfort",
        "comfort_plus",
        "auto",
        "antifrost",
        "standby",
    ],
    "RSS-ECTRL": [
        "setpoint",
        "boost",
        "eco",
        "comfort",
        "comfort_plus",
        "auto",
        "antifrost",
        "standby",
    ],
    "NTD": ["setpoint", "eco", "comfort", "auto", "antifrost", "standby"],
    "ETRV": ["setpoint", "eco", "comfort", "antifrost", "standby"],
}


class MyNeoClimate(ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "climate_myneomitis"

    def __init__(
        self, api: Any, device: dict[str, Any], all_devices: list[dict[str, Any]]
    ) -> None:
        self._api = api
        self._device = device
        self._all_devices = all_devices
        self._attr_unique_id = device["_id"]
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, device["_id"])},
            name=device["name"],
            manufacturer="Axenco",
            model=device["model"],
        )
        self._attr_available = device["connected"]
        self._unavailable_logged: bool = False

        state = device.get("state", {})
        self._is_sub_device = device["model"] in SUPPORTED_SUB_MODELS
        self._parents = device.get("parents", {})
        self._attr_preset_modes = PRESET_MODE_MODELES.get(device["model"], [])
        self._attr_min_temp = state.get("comfLimitMin", 7)
        self._attr_max_temp = state.get("comfLimitMax", 30)
        self._attr_current_temperature = state.get("currentTemp")
        self._attr_target_temperature = (
            state.get("targetTemp")
            if self._is_sub_device
            else state.get("overrideTemp")
        )
        target_mode = state.get("targetMode")
        self._attr_preset_mode = (
            REVERSE_PRESET_MODE_MAP.get(int(target_mode))
            if isinstance(target_mode, int)
            else None
        )
        # HVAC modes
        if device["model"] == "NTD" and state.get("changeOverUser") == 1:
            self._attr_hvac_modes = [HVACMode.COOL, HVACMode.OFF]
            self._attr_hvac_mode = (
                HVACMode.OFF
                if PRESET_MODE_MAP.get(self._attr_preset_mode or "") == 4
                else HVACMode.COOL
            )
        else:
            self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
            self._attr_hvac_mode = (
                HVACMode.OFF
                if PRESET_MODE_MAP.get(self._attr_preset_mode or "") == 4
                else HVACMode.HEAT
            )

        api.register_listener(device["_id"], self.handle_ws_update)

    @callback
    def handle_ws_update(self, new_state: dict[str, Any]) -> None:
        if not new_state:
            return

        if "connected" in new_state:
            self._attr_available = new_state["connected"]
            if not self._attr_available:
                if not self._unavailable_logged:
                    _LOGGER.info("The entity %s is unavailable", self.entity_id)
                    self._unavailable_logged = True
            elif self._unavailable_logged:
                _LOGGER.info("The entity %s is back online", self.entity_id)
                self._unavailable_logged = False

        if "currentTemp" in new_state:
            self._attr_current_temperature = new_state["currentTemp"]
        if "overrideTemp" in new_state:
            self._attr_target_temperature = new_state["overrideTemp"]
        elif "targetTemp" in new_state:
            self._attr_target_temperature = new_state["targetTemp"]
        if "targetMode" in new_state:
            self._attr_preset_mode = REVERSE_PRESET_MODE_MAP.get(
                new_state["targetMode"]
            )
            if self._attr_preset_mode == "standby":
                self._attr_hvac_mode = HVACMode.OFF
            elif self._attr_hvac_mode == HVACMode.OFF:
                self._attr_hvac_mode = HVACMode.HEAT
        if "changeOverUser" in new_state and self._device["model"] == "NTD":
            if new_state["changeOverUser"] == 1:
                self._attr_hvac_modes = [HVACMode.COOL, HVACMode.OFF]
                self._attr_hvac_mode = HVACMode.COOL
            else:
                self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
                self._attr_hvac_mode = HVACMode.HEAT
        self.async_write_ha_state()

    @property
    def supported_features(self) -> ClimateEntityFeature:
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        if self._attr_preset_mode != "setpoint":
            await self._set_device_mode("setpoint")
            self._attr_preset_mode = "setpoint"
        await self._set_device_temperature(temperature)
        self._attr_target_temperature = temperature
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode != "standby" and self._attr_hvac_mode == HVACMode.OFF:
            self._attr_hvac_mode = HVACMode.HEAT
        if self._attr_hvac_mode == HVACMode.OFF:
            return
        if preset_mode == "standby":
            self._attr_hvac_mode = HVACMode.OFF
        mode_value = PRESET_MODE_MAP.get(preset_mode)
        if mode_value is None:
            _LOGGER.warning("Unknown preset mode: %s", preset_mode)
            return
        await self._set_device_mode(preset_mode)
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            self._attr_preset_mode = "standby"
            await self._set_device_mode("standby")
        else:
            self._attr_preset_mode = "auto"
            await self._set_device_mode("auto")
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def _set_device_mode(self, mode: str) -> None:
        if self._is_sub_device:
            await self._api.set_sub_device_mode(
                self._parents["gateway"],
                str(self._device["rfid"]),
                PRESET_MODE_MAP[mode],
            )
        else:
            await self._api.set_device_mode(self._device["_id"], PRESET_MODE_MAP[mode])

    async def _set_device_temperature(self, temperature: float) -> None:
        if self._is_sub_device:
            await self._api.set_sub_device_temperature(
                self._parents["gateway"], str(self._device["rfid"]), temperature
            )
        else:
            await self._api.set_device_temperature(self._device["_id"], temperature)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyNeomitisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    api = config_entry.runtime_data.api
    devices = config_entry.runtime_data.devices

    def _create_entity(device: dict) -> MyNeoClimate:
        return MyNeoClimate(api, device, devices)

    climate_entities = [
        _create_entity(device)
        for device in devices
        if device["model"] in SUPPORTED_MODELS | SUPPORTED_SUB_MODELS
    ]
    async_add_entities(climate_entities)
