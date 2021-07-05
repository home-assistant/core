"""Support for Freedompro climate."""
import json

from pyfreedompro import put_state

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)
from homeassistant.components.water_heater import SUPPORT_TARGET_TEMPERATURE
from homeassistant.const import ATTR_TEMPERATURE, CONF_API_KEY, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro climate."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if device["type"] == "thermostat"
    )


class Device(CoordinatorEntity, ClimateEntity):
    """Representation of an Freedompro climate."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro climate."""
        super().__init__(coordinator)
        self._hass = hass
        self._session = aiohttp_client.async_get_clientsession(self._hass)
        self._api_key = api_key
        self._attr_name = device["name"]
        self._attr_unique_id = device["uid"]
        self._type = device["type"]
        self._characteristics = device["characteristics"]
        self._attr_device_info = {
            "name": self._attr_name,
            "identifiers": {
                (DOMAIN, self._attr_unique_id),
            },
            "model": self._type,
            "manufacturer": "Freedompro",
        }
        self._attr_supported_features = SUPPORT_TARGET_TEMPERATURE
        self._attr_current_temperature = 0
        self._attr_target_temperature = 0
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_hvac_mode = HVAC_MODE_OFF
        self._attr_hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_COOL]

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
                self._attr_hvac_mode = (
                    HVAC_MODE_OFF
                    if state["heatingCoolingState"] == 0
                    else HVAC_MODE_HEAT
                    if state["heatingCoolingState"] == 1
                    else HVAC_MODE_COOL
                )
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_set_hvac_mode(self, hvac_mode):
        """Async function to set mode to climate."""
        payload = {}
        payload["heatingCoolingState"] = (
            0 if hvac_mode == HVAC_MODE_OFF else 1 if hvac_mode == HVAC_MODE_HEAT else 2
        )
        payload = json.dumps(payload)
        await put_state(
            self._session,
            self._api_key,
            self._attr_unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs):
        """Async function to set temperarture to climate."""
        payload = {}
        if ATTR_TEMPERATURE in kwargs:
            payload["targetTemperature"] = kwargs[ATTR_TEMPERATURE]
        payload = json.dumps(payload)
        await put_state(
            self._session,
            self._api_key,
            self._attr_unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()
