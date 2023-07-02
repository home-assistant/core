"""Support for Freedompro climate."""
from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp.client import ClientSession
from pyfreedompro import put_state

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, CONF_API_KEY, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreedomproDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

HVAC_MAP = {
    0: HVACMode.OFF,
    1: HVACMode.HEAT,
    2: HVACMode.COOL,
}

HVAC_INVERT_MAP = {v: k for k, v in HVAC_MAP.items()}

SUPPORTED_HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.HEAT,
    HVACMode.COOL,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Freedompro climate."""
    api_key: str = entry.data[CONF_API_KEY]
    coordinator: FreedomproDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(
            aiohttp_client.async_get_clientsession(hass), api_key, device, coordinator
        )
        for device in coordinator.data
        if device["type"] == "thermostat"
    )


class Device(CoordinatorEntity[FreedomproDataUpdateCoordinator], ClimateEntity):
    """Representation of a Freedompro climate."""

    _attr_has_entity_name = True
    _attr_hvac_modes = SUPPORTED_HVAC_MODES
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_name = None
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_current_temperature = 0
    _attr_target_temperature = 0
    _attr_hvac_mode = HVACMode.OFF

    def __init__(
        self,
        session: ClientSession,
        api_key: str,
        device: dict[str, Any],
        coordinator: FreedomproDataUpdateCoordinator,
    ) -> None:
        """Initialize the Freedompro climate."""
        super().__init__(coordinator)
        self._session = session
        self._api_key = api_key
        self._attr_unique_id = device["uid"]
        self._characteristics = device["characteristics"]
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, device["uid"]),
            },
            manufacturer="Freedompro",
            model=device["type"],
            name=device["name"],
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = next(
            (
                device
                for device in self.coordinator.data
                if device["uid"] == self._attr_unique_id
            ),
            None,
        )
        if device is not None and "state" in device:
            state = device["state"]
            if "currentTemperature" in state:
                self._attr_current_temperature = state["currentTemperature"]
            if "targetTemperature" in state:
                self._attr_target_temperature = state["targetTemperature"]
            if "heatingCoolingState" in state:
                self._attr_hvac_mode = HVAC_MAP[state["heatingCoolingState"]]
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Async function to set mode to climate."""
        if hvac_mode not in SUPPORTED_HVAC_MODES:
            raise ValueError(f"Got unsupported hvac_mode {hvac_mode}")

        payload = {"heatingCoolingState": HVAC_INVERT_MAP[hvac_mode]}
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            json.dumps(payload),
        )
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Async function to set temperature to climate."""
        payload = {}
        if ATTR_HVAC_MODE in kwargs:
            if kwargs[ATTR_HVAC_MODE] not in SUPPORTED_HVAC_MODES:
                _LOGGER.error(
                    "Got unsupported hvac_mode %s, expected one of %s",
                    kwargs[ATTR_HVAC_MODE],
                    SUPPORTED_HVAC_MODES,
                )
                return
            payload["heatingCoolingState"] = HVAC_INVERT_MAP[kwargs[ATTR_HVAC_MODE]]
        if ATTR_TEMPERATURE in kwargs:
            payload["targetTemperature"] = kwargs[ATTR_TEMPERATURE]
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            json.dumps(payload),
        )
        await self.coordinator.async_request_refresh()
