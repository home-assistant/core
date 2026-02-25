"""Climate entities for MyNeomitis integration."""

from __future__ import annotations

import logging
from typing import Any

from pyaxencoapi import PyAxencoAPI

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MyNeomitisConfigEntry, process_connection_update
from .const import DOMAIN, PRESET_MODE_MAP, PRESET_MODE_MODELS, REVERSE_PRESET_MODE_MAP

_LOGGER = logging.getLogger(__name__)

SUPPORTED_MODELS: frozenset[str] = frozenset({"EV30", "ECTRL", "ESTAT", "RSS-ECTRL"})
SUPPORTED_SUB_MODELS: frozenset[str] = frozenset({"NTD", "ETRV"})


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyNeomitisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate entities from a config entry."""
    api = config_entry.runtime_data.api
    devices = config_entry.runtime_data.devices

    def _create_entity(device: dict) -> MyNeoClimate:
        return MyNeoClimate(api, device)

    climate_entities = [
        _create_entity(device)
        for device in devices
        if device.get("model") in SUPPORTED_MODELS | SUPPORTED_SUB_MODELS
    ]
    async_add_entities(climate_entities)


class MyNeoClimate(ClimateEntity):
    """Climate entity for MyNeomitis device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_should_poll = False

    def __init__(self, api: PyAxencoAPI, device: dict[str, Any]) -> None:
        """Initialize the MyNeoClimate entity."""
        self._api = api
        self._device = device
        device_id: str = device.get("_id") or ""
        model = device.get("model", "")
        name = device.get("name") or device_id or "MyNeomitis device"
        connected = bool(device.get("connected", False))

        self._attr_unique_id = device_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=name,
            manufacturer="Axenco",
            model=model,
        )

        self._attr_available = connected
        self._unavailable_logged: bool = False

        state = device.get("state", {})
        self._is_sub_device = model in SUPPORTED_SUB_MODELS
        self._parents = device.get("parents") or {}
        self._attr_preset_modes: list[str] = PRESET_MODE_MODELS.get(model, [])
        self._attr_min_temp = state.get("comfLimitMin", 7)
        self._attr_max_temp = state.get("comfLimitMax", 30)
        self._attr_current_temperature = state.get("currentTemp")
        self._attr_target_temperature = (
            state.get("targetTemp")
            if self._is_sub_device
            else state.get("overrideTemp")
        )
        target_mode = state.get("targetMode")
        if isinstance(target_mode, int):
            self._attr_preset_mode = REVERSE_PRESET_MODE_MAP.get(int(target_mode))
        else:
            self._attr_preset_mode = None
        self._last_preset_mode: str | None = (
            self._attr_preset_mode
            if self._attr_preset_mode and self._attr_preset_mode != "standby"
            else None
        )
        if model == "NTD" and state.get("changeOverUser") == 1:
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

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )

    async def async_added_to_hass(self) -> None:
        """Register listener when entity is added to hass."""
        await super().async_added_to_hass()
        device_id = self._device.get("_id")
        if not device_id:
            return

        try:
            unsubscribe = self._api.register_listener(device_id, self.handle_ws_update)
        except AttributeError:
            _LOGGER.debug(
                "API has no register_listener, skipping ws listener for %s", device_id
            )
        else:
            if callable(unsubscribe):
                self.async_on_remove(unsubscribe)
            elif hasattr(unsubscribe, "unsubscribe"):
                self.async_on_remove(unsubscribe.unsubscribe)
            elif hasattr(unsubscribe, "close"):
                self.async_on_remove(unsubscribe.close)
            elif unsubscribe is None:
                pass
            else:
                _LOGGER.debug(
                    "register_listener returned unsupported type %s for %s",
                    type(unsubscribe),
                    device_id,
                )

    @callback
    def handle_ws_update(self, new_state: dict[str, Any]) -> None:
        """Update entity state from WebSocket callback."""
        available = process_connection_update(new_state)
        if available is not None:
            self._attr_available = available
            if not available:
                if not getattr(self, "_unavailable_logged", False):
                    _LOGGER.info("The entity %s is unavailable", self.entity_id)
                    self._unavailable_logged = True
            elif getattr(self, "_unavailable_logged", False):
                _LOGGER.info("The entity %s is back online", self.entity_id)
                self._unavailable_logged = False

        if not new_state:
            return

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
            if self._attr_preset_mode and self._attr_preset_mode != "standby":
                self._last_preset_mode = self._attr_preset_mode
            if self._attr_preset_mode == "standby":
                self._attr_hvac_mode = HVACMode.OFF
            elif self._attr_hvac_mode == HVACMode.OFF:
                self._attr_hvac_mode = next(
                    (
                        mode
                        for mode in self._attr_hvac_modes
                        if mode is not HVACMode.OFF
                    ),
                    HVACMode.HEAT,
                )
        if "changeOverUser" in new_state and self._device.get("model") == "NTD":
            if new_state["changeOverUser"] == 1:
                self._attr_hvac_modes = [HVACMode.COOL, HVACMode.OFF]
                self._attr_hvac_mode = HVACMode.COOL
            else:
                self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
                self._attr_hvac_mode = HVACMode.HEAT
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature for the climate entity."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        if self._attr_preset_mode != "setpoint":
            ok = await self._set_device_mode("setpoint")
            if not ok:
                raise HomeAssistantError(
                    f"Failed to set preset mode 'setpoint' for {self.entity_id}"
                )
            self._attr_preset_mode = "setpoint"

        ok = await self._set_device_temperature(temperature)
        if not ok:
            raise HomeAssistantError(
                f"Failed to set temperature to {temperature} for {self.entity_id}"
            )

        self._attr_target_temperature = temperature
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode for the climate entity."""
        if preset_mode == "standby":
            self._attr_hvac_mode = HVACMode.OFF
        elif self._attr_hvac_mode == HVACMode.OFF:
            # When leaving standby, select the first supported non-OFF HVAC mode
            next_mode: HVACMode | None = None
            if getattr(self, "_attr_hvac_modes", None):
                next_mode = next(
                    (mode for mode in self._attr_hvac_modes if mode != HVACMode.OFF),
                    None,
                )
            if next_mode is not None:
                self._attr_hvac_mode = next_mode
        mode_value = PRESET_MODE_MAP.get(preset_mode)
        if mode_value is None:
            _LOGGER.warning("Unknown preset mode: %s", preset_mode)
            return
        ok = await self._set_device_mode(preset_mode)
        if not ok:
            raise HomeAssistantError(
                f"Failed to set preset mode '{preset_mode}' for {self.entity_id}"
            )

        if preset_mode != "standby":
            self._last_preset_mode = preset_mode

        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode for the climate entity."""
        if hvac_mode == HVACMode.OFF:
            if self._attr_preset_mode and self._attr_preset_mode != "standby":
                self._last_preset_mode = self._attr_preset_mode

            ok = await self._set_device_mode("standby")
            if not ok:
                raise HomeAssistantError(
                    f"Failed to set standby mode for {self.entity_id}"
                )
            self._attr_preset_mode = "standby"
        else:
            preset_to_restore = None
            if (
                self._last_preset_mode
                and self._last_preset_mode in self._attr_preset_modes
            ):
                preset_to_restore = self._last_preset_mode

            if not preset_to_restore:
                for candidate in ("comfort", "setpoint", "eco", "auto"):
                    if candidate in self._attr_preset_modes and candidate != "standby":
                        preset_to_restore = candidate
                        break

            if not preset_to_restore:
                preset_to_restore = next(
                    (p for p in self._attr_preset_modes if p != "standby"), "auto"
                )

            ok = await self._set_device_mode(preset_to_restore)
            if not ok:
                raise HomeAssistantError(
                    f"Failed to restore preset '{preset_to_restore}' for {self.entity_id}"
                )
            self._attr_preset_mode = preset_to_restore

        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def _set_device_mode(self, mode: str) -> bool:
        """Set the device mode via API."""
        try:
            mode_value = PRESET_MODE_MAP.get(mode)
            if mode_value is None:
                _LOGGER.error(
                    "Attempt to set unknown mode %s for %s", mode, self.entity_id
                )
                return False

            if self._is_sub_device:
                gateway = self._parents.get("gateway")
                rfid = self._device.get("rfid")
                if not gateway or not rfid:
                    _LOGGER.error(
                        "Missing gateway or rfid for sub-device %s, cannot set mode",
                        self._attr_unique_id,
                    )
                    return False
                await self._api.set_sub_device_mode(gateway, str(rfid), mode_value)
            else:
                device_id = self._device.get("_id")
                if not device_id:
                    _LOGGER.error("Missing device id for device, cannot set mode")
                    return False
                await self._api.set_device_mode(device_id, mode_value)
        except (TimeoutError, ConnectionError) as err:
            _LOGGER.error(
                "Error setting device mode for %s: %s", self._device.get("_id"), err
            )
            return False

        return True

    async def _set_device_temperature(self, temperature: float) -> bool:
        """Set the device temperature via API."""
        try:
            if self._is_sub_device:
                gateway = self._parents.get("gateway")
                rfid = self._device.get("rfid")
                if not gateway or not rfid:
                    _LOGGER.error(
                        "Missing gateway or rfid for sub-device %s, cannot set temperature",
                        self._attr_unique_id,
                    )
                    return False
                await self._api.set_sub_device_temperature(
                    gateway, str(rfid), temperature
                )
            else:
                device_id = self._device.get("_id")
                if not device_id:
                    _LOGGER.error(
                        "Missing device id for device, cannot set temperature"
                    )
                    return False
                await self._api.set_device_temperature(device_id, temperature)
        except (TimeoutError, ConnectionError) as err:
            _LOGGER.error(
                "Error setting device temperature for %s: %s",
                self._device.get("_id"),
                err,
            )
            return False

        return True
