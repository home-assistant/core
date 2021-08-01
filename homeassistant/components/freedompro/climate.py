"""Support for Freedompro climate."""
import json
import logging

from pyfreedompro import put_state

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_API_KEY, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

HVAC_MAP = {
    0: HVAC_MODE_OFF,
    1: HVAC_MODE_HEAT,
    2: HVAC_MODE_COOL,
}

HVAC_INVERT_MAP = {v: k for k, v in HVAC_MAP.items()}

SUPPORTED_HVAC_MODES = [HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_COOL]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro climate."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(
            aiohttp_client.async_get_clientsession(hass), api_key, device, coordinator
        )
        for device in coordinator.data
        if device["type"] == "thermostat"
    )


class Device(CoordinatorEntity, ClimateEntity):
    """Representation of an Freedompro climate."""

    _attr_hvac_modes = SUPPORTED_HVAC_MODES
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(self, session, api_key, device, coordinator):
        """Initialize the Freedompro climate."""
        super().__init__(coordinator)
        self._session = session
        self._api_key = api_key
        self._attr_name = device["name"]
        self._attr_unique_id = device["uid"]
        self._characteristics = device["characteristics"]
        self._attr_device_info = {
            "name": self.name,
            "identifiers": {
                (DOMAIN, self.unique_id),
            },
            "model": device["type"],
            "manufacturer": "Freedompro",
        }
        self._attr_supported_features = SUPPORT_TARGET_TEMPERATURE
        self._attr_current_temperature = 0
        self._attr_target_temperature = 0
        self._attr_hvac_mode = HVAC_MODE_OFF

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

    async def async_set_hvac_mode(self, hvac_mode):
        """Async function to set mode to climate."""
        if hvac_mode not in SUPPORTED_HVAC_MODES:
            raise ValueError(f"Got unsupported hvac_mode {hvac_mode}")

        payload = {}
        payload["heatingCoolingState"] = HVAC_INVERT_MAP[hvac_mode]
        payload = json.dumps(payload)
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs):
        """Async function to set temperarture to climate."""
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
        payload = json.dumps(payload)
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()
