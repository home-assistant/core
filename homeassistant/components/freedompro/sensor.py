"""Support for Freedompro sensor."""
from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    SensorEntity,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro sensor."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if device["type"] == "temperatureSensor"
        or device["type"] == "humiditySensor"
        or device["type"] == "lightSensor"
    )


class Device(CoordinatorEntity, SensorEntity):
    """Representation of an Freedompro sensor."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro sensor."""
        super().__init__(coordinator)
        self._hass = hass
        self._session = aiohttp_client.async_get_clientsession(self._hass)
        self._api_key = api_key
        self._attr_name = device["name"]
        self._attr_unique_id = device["uid"]
        self._type = device["type"]
        self._characteristics = device["characteristics"]
        self._attr_device_class = (
            DEVICE_CLASS_TEMPERATURE
            if self._type == "temperatureSensor"
            else DEVICE_CLASS_HUMIDITY
            if self._type == "humiditySensor"
            else DEVICE_CLASS_ILLUMINANCE
        )
        self._attr_state = 0

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
            if "currentAmbientLightLevel" in state:
                self._attr_state = state["currentAmbientLightLevel"]
            if "currentRelativeHumidity" in state:
                self._attr_state = state["currentRelativeHumidity"]
            if "currentTemperature" in state:
                self._attr_state = state["currentTemperature"]
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
