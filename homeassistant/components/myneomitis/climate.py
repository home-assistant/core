"""Climate platform for MyNeomitis integration.

This module defines the MyNeoClimate entity and its setup for Home Assistant.
"""

import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import callback

from .const import DOMAIN
from .logger import log_api_update, log_ws_update
from .utils import (
    PRESET_MODE_MAP,
    REVERSE_PRESET_MODE_MAP,
    format_week_schedule,
    get_device_by_rfid,
    parents_to_dict,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS: int = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
HVAC_MODES: list[str] = [HVACMode.HEAT, HVACMode.OFF]
COOL_MODES: list[str] = [HVACMode.COOL, HVACMode.OFF]

MODELES: list[str] = ["EV30", "ECTRL", "ESTAT", "RSS-ECTRL"]
SUB_MODELES: list[str] = ["NTD", "ETRV"]

PRESET_MODE_MODELES: dict[str, list[str]] = {
    "EV30": ["setpoint", "boost", "eco", "comfort", "auto", "antifrost", "standby"],
    "ECTRL": ["setpoint", "boost", "eco", "comfort", "comfort +", "auto", "antifrost", "standby"],
    "ESTAT": ["setpoint", "boost", "eco", "comfort", "comfort +", "auto", "antifrost", "standby"],
    "RSS-ECTRL": ["setpoint", "boost", "eco", "comfort", "comfort +", "auto", "antifrost", "standby"],
    "NTD": ["setpoint", "eco", "comfort", "auto", "antifrost", "standby"],
    "ETRV": ["setpoint", "eco", "comfort", "antifrost", "standby"],
}


class MyNeoClimate(ClimateEntity):
    """Climate entity for MyNeomitis device.

    This class provides support for controlling devices, including
    setting target temperatures, preset modes, and HVAC modes. It also
    retrieves and updates the current state of the device.
    """

    def __init__(self, api: Any, device: dict[str, Any], devices: list[dict[str, Any]]) -> None:
        """Initialize the MyNeoClimate entity.

        Args:
            api (Any): The API instance used for communication with the device.
            device (dict[str, Any]): The dictionary containing device information and state.
            devices (list[dict[str, Any]]): A list of all devices associated with the integration.

        """
        self._api = api
        self._device = device
        state = device.get("state", {})
        self._parents = parents_to_dict(device["parents"]) if "parents" in device else {}
        self._primary_parent = get_device_by_rfid(devices, self._parents["primary"]) if "primary" in self._parents else {}
        self._is_sub_device = device["model"] in SUB_MODELES
        self._attr_available = device["connected"]
        self._attr_name = f"MyNeo {device['name']}"
        self._attr_unique_id = f"myneo_{device['_id']}"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        self._attr_target_temperature = state.get("targetTemp") if self._is_sub_device else state.get("overrideTemp")
        self._attr_current_temperature = state.get("currentTemp")
        self._attr_min_temp = state.get("comfLimitMin", 7)
        self._attr_max_temp = state.get("comfLimitMax", 30)

        self._attr_translation_key = "climate_myneomitis"

        self._attr_preset_modes = PRESET_MODE_MODELES.get(device["model"], [])
        self._attr_preset_mode = REVERSE_PRESET_MODE_MAP.get(state.get("targetMode"))
        if device["model"] == "NTD" and self._primary_parent.get("state", {}).get("changeOverUser", {}) == 1:
            self._attr_hvac_modes = COOL_MODES
            self._attr_hvac_mode = HVACMode.OFF if PRESET_MODE_MAP.get(self._attr_preset_mode) == 4 else HVACMode.COOL
        else:
            self._attr_hvac_modes = HVAC_MODES
            self._attr_hvac_mode = HVACMode.OFF if PRESET_MODE_MAP.get(self._attr_preset_mode) == 4 else HVACMode.HEAT

        self._program = device.get("program", {}).get("data", {})

        api.register_listener(device["_id"], self.handle_ws_update)

    @callback
    def handle_ws_update(self, new_state: dict[str, Any]) -> None:
        """Update the local state from a WebSocket message.

        Args:
            new_state (dict[str, Any]): The new state received from the WebSocket.

        """
        state = new_state
        if not state:
            return

        self._attr_current_temperature = state.get("currentTemp", self._attr_current_temperature)

        if "connected" in state:
            self._attr_available = state["connected"]

        if "program" in state:
            new_data = state["program"].get("data", {})
            self._program.update(new_data)

        if "name" in state:
            self._attr_name = state["name"]

        if "overrideTemp" in state:
            self._attr_target_temperature = state["overrideTemp"]
        elif "targetTemp" in state:
            self._attr_target_temperature = state["targetTemp"]

        if "changeOverUser" in state:
            if state["changeOverUser"] == 0:
                self._attr_hvac_modes = HVAC_MODES
                self._attr_hvac_mode = HVACMode.HEAT
            elif state["changeOverUser"] == 1:
                self._attr_hvac_modes = COOL_MODES
                self._attr_hvac_mode = HVACMode.COOL

        if "targetMode" in state:
            self._attr_preset_mode = REVERSE_PRESET_MODE_MAP.get(state["targetMode"])

            if self._attr_preset_mode != "standby" and self._attr_hvac_mode == HVACMode.OFF:
                self._attr_hvac_mode = HVACMode.HEAT
            if self._attr_preset_mode == "standby":
                self._attr_hvac_mode = HVACMode.OFF

        log_ws_update(self._attr_name, state)
        self.async_write_ha_state()

    @property
    def supported_features(self) -> int:
        """Return the supported features of the climate.

        Returns:
            int: Supported features as a bitmask.

        """
        return SUPPORT_FLAGS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes for the climate.

        Returns:
            dict[str, Any]: Extra state attributes including WebSocket status and weekly planning.

        """
        attributes = {
            "ws_status": "connected" if self._api.sio.connected else "disconnected",
            "is_connected": "True" if self._attr_available else "False"

        }

        if self._program:
            week_planning = format_week_schedule(self._program)
            for day, planning in week_planning.items():
                attributes[f"planning_{day.lower()}"] = planning

        return attributes

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature for the climate.

        Args:
            **kwargs (Any): Keyword arguments containing the target temperature (ATTR_TEMPERATURE).

        """
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        if self._attr_preset_mode != "setpoint":
            await self.set_api_device_mode("setpoint")
            self._attr_preset_mode = "setpoint"

        await self.set_api_device_temperature(temperature)

        self._attr_target_temperature = temperature
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode for the climate.

        Args:
            preset_mode (str): The desired preset mode to set (e.g., "eco", "comfort", etc.).

        """
        if preset_mode != "standby" and self._attr_hvac_mode == HVACMode.OFF:
            self._attr_hvac_mode = HVACMode.HEAT

        if self._attr_hvac_mode == HVACMode.OFF:
            return

        if preset_mode == "standby":
            self._attr_hvac_mode = HVACMode.OFF

        mode_value = PRESET_MODE_MAP.get(preset_mode)
        if mode_value is None:
            _LOGGER.warning("MyNeomitis : Unknown preset mode: %s", preset_mode)
            return
        await self.set_api_device_mode(preset_mode)

        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set the HVAC mode for the climate.

        Args:
            hvac_mode (str): The desired HVAC mode to set (e.g., "heat", "off").

        """
        if hvac_mode == HVACMode.OFF:
            self._attr_preset_mode = "standby"
            await self.set_api_device_mode("standby")
        else:
            self._attr_preset_mode = "auto"
            await self.set_api_device_mode("auto")

        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch the latest state of the climate from the API."""
        state = await self.get_api_device_state()
        if not state:
            return

        current = state["state"]

        log_api_update(self._attr_name, current)

        self._attr_current_temperature = current.get("currentTemp", self._attr_current_temperature)
        self.async_write_ha_state()

    async def set_api_device_mode(self, mode: str) -> Any:
        """Set the device mode for the climate.

        Args:
            mode (str): The desired mode to set for the device.

        Returns:
            Any: The result of the API call to set the device mode.

        """
        if self._is_sub_device:
            return await self._api.set_sub_device_mode(self._parents["gateway"], self._device["rfid"], PRESET_MODE_MAP[mode])

        return await self._api.set_device_mode(self._device["_id"], PRESET_MODE_MAP[mode])

    async def set_api_device_temperature(self, temperature: float) -> Any:
        """Set the target temperature for the device.

        Args:
            temperature (float): The desired temperature to set for the device.

        Returns:
            Any: The result of the API call to set the device temperature.

        """
        if self._is_sub_device:
            return await self._api.set_sub_device_temperature(self._parents["gateway"], self._device["rfid"], temperature)

        return await self._api.set_device_temperature(self._device["_id"], temperature)

    async def get_api_device_state(self) -> dict[str, Any] | None:
        """Retrieve the state of the device from the API.

        Returns:
            Optional[dict[str, Any]]: The state of the device retrieved from the API.

        """
        if self._is_sub_device:
            response = await self._api.get_sub_device_state(self._parents["gateway"])
            return get_device_by_rfid(response, self._device["rfid"])

        return await self._api.get_device_state(self._device["_id"])


async def async_setup_entry(hass: Any, config_entry: Any, async_add_entities: Any) -> None:
    """Set up climate entities from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        config_entry (ConfigEntry): The configuration entry.
        async_add_entities (AddEntitiesCallback): Callback to add entities.

    """
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    api = entry_data["api"]
    devices = entry_data["devices"]

    added_ids = set()
    entities_by_id: dict[str, MyNeoClimate] = {}

    def _create_entity(device: dict) -> MyNeoClimate:
        entity = MyNeoClimate(api, device, [*devices, device])
        added_ids.add(device["_id"])
        entities_by_id[f"myneo_{device['_id']}"] = entity
        return entity

    climate_entities = [
        _create_entity(device)
        for device in devices
        if device["model"] in MODELES or device["model"] in SUB_MODELES
    ]

    async_add_entities(climate_entities)

    async def add_new_entity(device: dict) -> None:
        if device["_id"] in added_ids:
            return
        entity = _create_entity(device)
        _LOGGER.info("MyNeomitis : Adding new climate entity: %s", entity.name)
        async_add_entities([entity])

    async def remove_entity(device_id: str) -> None:
        uid = f"myneo_{device_id}"
        entity = entities_by_id.get(uid)
        if entity:
            _LOGGER.info("MyNeomitis : Removing climate entity: %s", uid)
            await entity.async_remove()
            added_ids.discard(device_id)
            entities_by_id.pop(uid, None)

    api.register_discovery_callback(lambda dev: hass.async_create_task(add_new_entity(dev)))
    api.register_removal_callback(lambda dev_id: hass.async_create_task(remove_entity(dev_id)))


