"""Module for IoTMeter number entities in Home Assistant."""

import logging

import requests

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IoTMeter number entities from a config entry."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    coordinator.async_add_number_entities = (
        async_add_entities  # Store the function in the coordinator
    )
    hass.data[DOMAIN]["platform"] = async_add_entities
    _LOGGER.debug("async_add_entities set in coordinator")
    await coordinator.async_request_refresh()


class ChargingCurrentNumber(CoordinatorEntity, NumberEntity):
    """Representation of a current slider."""

    def __init__(
        self,
        coordinator,
        sensor_type,
        translations,
        unit_of_measurement,
        min_value,
        max_value,
        step,
        fw_version="Unknown",
        smartmodule: bool = False,
    ) -> None:
        """Initialize the current slider."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type.replace(" ", "_").lower()
        self._translations = translations
        self._attr_name = self.get_localized_name()
        self._attr_unique_id = f"iotmeter_{self._sensor_type}"
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_value = min_value
        self._coordinator = coordinator
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._evse_current = 0
        self._fw_version: str = fw_version
        self._smartmodule: bool = smartmodule

    def get_localized_name(self):
        """Return the localized name for the sensor."""
        key = f"component.iotmeter.entity.sensor.{self._sensor_type}"
        localized_name = self._translations.get(key)
        return localized_name or self._sensor_type

    @property
    def state(self):
        """Return the current state."""
        evse_current = self.coordinator.data.get("EVSE_CURRENT")
        if evse_current is not None:
            self._evse_current = evse_current
        return self._evse_current

    async def async_set_native_value(self, value):
        """Set the current value."""
        self._attr_native_value = value
        self._evse_current = value
        await self.hass.async_add_executor_job(self.update_evse_current, value)

    def update_evse_current(self, value):
        """Update the EVSE current via HTTP request."""
        try:
            self._evse_current = value

            response = requests.post(
                url=f"http://{self._coordinator.ip_address}:{self._coordinator.port}/updateRamSetting",
                json={"variable": "EVSE_CURRENT", "value": self._evse_current},
                timeout=5,
            )
            response.raise_for_status()

        except requests.RequestException as err:
            _LOGGER.error("Error setting EVSE current: %s", err)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        device = "Smartmodule" if self._smartmodule else "IoTMeter"
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id or "")},
            name="iotmeter",
            manufacturer="Vilmio",
            model=device,
            sw_version=self._fw_version,
            via_device=(DOMAIN, "iotmeter"),
        )

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:power-plug"
