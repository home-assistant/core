"""Support for Appartme thermostat control functionality."""

import logging

from homeassistant.components import logbook
from homeassistant.components.climate import (
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_logbook_translation
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Appartme climate platform."""
    # Access the devices and API from hass.data
    data = hass.data[DOMAIN][config_entry.entry_id]
    devices_info = data["devices_info"]
    api = data["api"]
    translations = data["translations"]
    coordinators = data["coordinators"]

    # Create climate entities for the thermostat
    thermostats = []
    for device_info in devices_info:
        device_id = device_info["deviceId"]
        coordinator = coordinators.get(device_id)
        if not coordinator:
            _LOGGER.warning("No coordinator found for device %s. Skipping", device_id)
            continue

        thermostats.extend(
            [
                AppartmeThermostat(
                    api,
                    device_info,
                    prop["propertyId"],
                    translations,
                    coordinator,
                )
                for prop in device_info.get("properties", [])
                if prop["propertyId"] == "thermostat_mode"
            ]
        )

    if not thermostats:
        _LOGGER.warning("No thermostat entities to add")
        return

    # Add the thermostat entities to Home Assistant
    async_add_entities(thermostats)


class AppartmeThermostat(CoordinatorEntity, ClimateEntity):
    """Representation of an Appartme thermostat."""

    def __init__(self, api, device_info, property_id, translations, coordinator):
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self._api = api
        self._device_id = device_info["deviceId"]
        self._device_name = device_info["name"]
        self._property_id = property_id
        self._attr_translation_key = property_id
        self._attr_has_entity_name = True
        self._translations = translations

        # Optimistic state attributes
        self._attr_preset_mode = None
        self._attr_target_temperature = None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link this entity to a device."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": "Appartme",
            "model": "Main Module",
            "sw_version": self._device_id,
        }

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{self._device_id}_{self._property_id}"

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC operation modes."""
        return [HVACMode.HEAT]  # Only HEAT mode is supported

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current HVAC mode."""
        return HVACMode.HEAT

    @property
    def preset_modes(self) -> list[str]:
        """Return the available preset modes."""
        return [PRESET_ECO, PRESET_COMFORT]

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        # Because of optimistic update state
        if self._attr_preset_mode is not None:
            return self._attr_preset_mode

        data = self.coordinator.data
        if data is None:
            return None
        for prop in data.get("values", []):
            if prop["propertyId"] == "thermostat_mode":
                mode = prop["value"]
                if mode == "eco":
                    return PRESET_ECO
                if mode == "comfort":
                    return PRESET_COMFORT
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current room temperature."""
        data = self.coordinator.data
        if data is None:
            return None
        for prop in data.get("values", []):
            if prop["propertyId"] == "current_temperature":
                return float(prop["value"])
        return None

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature(self) -> float | None:
        """Return the current target temperature based on the preset mode."""
        # Because of optimistic update state
        if self._attr_target_temperature is not None:
            return self._attr_target_temperature

        data = self.coordinator.data
        if data is None:
            return None

        preset_mode = self.preset_mode
        if preset_mode == PRESET_ECO:
            property_id = "eco_temperature"
        elif preset_mode == PRESET_COMFORT:
            property_id = "comfort_temperature"
        else:
            return None

        for prop in data.get("values", []):
            if prop["propertyId"] == property_id:
                return float(prop["value"])
        return None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature that can be set."""
        # You can adjust these values or fetch from data if available
        return 10.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature that can be set."""
        # You can adjust these values or fetch from data if available
        return 30.0

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the supported features."""
        return (
            ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
        )

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new HVAC mode (No actual change since only HEAT is supported)."""
        if hvac_mode != HVACMode.HEAT:
            _LOGGER.error("Only HEAT mode is supported")
            return
        # No action needed; only HEAT mode is supported
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode (eco or comfort)."""
        if preset_mode == PRESET_ECO:
            value = "eco"
        elif preset_mode == PRESET_COMFORT:
            value = "comfort"
        else:
            _LOGGER.error("Invalid preset mode: %s", preset_mode)
            return

        try:
            await self._api.set_device_property_value(
                self._device_id, "thermostat_mode", value
            )
            # Optimistically update the preset mode
            self._attr_preset_mode = preset_mode

            # Log the change with translations
            logbook.async_log_entry(
                self.hass,
                name=f"{self.name}",
                message=get_logbook_translation(
                    self._translations,
                    "changed_preset_mode",
                    preset_mode=preset_mode,
                ),
                domain=DOMAIN,
                entity_id=self.entity_id,
            )

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error setting preset mode for %s: %s", self.name, err)
            # Reset the optimistic attribute
            self._attr_preset_mode = None
            # Notify the user
            self.hass.components.persistent_notification.create(
                f"Failed to set preset mode for {self.name}: {err}",
                title="Appartme System",
                notification_id=f"appartme_{self._device_id}_preset_error",
            )
        finally:
            # Force UI to refresh
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set the target temperature for the current preset mode."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            _LOGGER.error("No temperature provided")
            return

        preset_mode = self.preset_mode
        if preset_mode == PRESET_ECO:
            property_id = "eco_temperature"
        elif preset_mode == PRESET_COMFORT:
            property_id = "comfort_temperature"
        else:
            _LOGGER.error("Cannot set temperature when preset mode is unknown")
            return

        try:
            await self._api.set_device_property_value(
                self._device_id, property_id, temperature
            )
            # Optimistically update the target temperature
            self._attr_target_temperature = temperature

            # Log the change with translations
            logbook.async_log_entry(
                self.hass,
                name=f"{self.name}",
                message=get_logbook_translation(
                    self._translations,
                    "changed_target_temperature",
                    temperature=temperature,
                ),
                domain=DOMAIN,
                entity_id=self.entity_id,
            )

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error setting temperature for %s: %s", self.name, err)
            # Reset the optimistic attribute
            self._attr_target_temperature = None
            # Notify the user
            self.hass.components.persistent_notification.create(
                f"Failed to set temperature for {self.name}: {err}",
                title="Appartme System",
                notification_id=f"appartme_{self._device_id}_temperature_error",
            )
        finally:
            # Force UI to refresh
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Reset optimistic attributes
        self._attr_preset_mode = None
        self._attr_target_temperature = None
        self.async_write_ha_state()
