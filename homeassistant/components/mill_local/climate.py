"""Support for mill wifi-enabled home heaters."""

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_HEAT,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MAX_TEMP, MIN_TEMP

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Mill climate."""

    entities = [
        MillHeater(device_id, mill_data_coordinator)
        for device_id, mill_data_coordinator in hass.data[DOMAIN].items()
    ]
    async_add_entities(entities)


class MillHeater(CoordinatorEntity, ClimateEntity):
    """Representation of a Mill Thermostat device."""

    _attr_hvac_mode = HVAC_MODE_HEAT
    _attr_hvac_modes = [HVAC_MODE_HEAT]
    _attr_max_temp = MAX_TEMP
    _attr_min_temp = MIN_TEMP
    _attr_supported_features = SUPPORT_FLAGS
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(self, device_id, coordinator):
        """Initialize the thermostat."""

        super().__init__(coordinator)

        self._attr_name = coordinator.mill_data_connection.name
        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.mill_data_connection.url,
            identifiers={(DOMAIN, device_id)},
            manufacturer=MANUFACTURER,
            name=coordinator.mill_data_connection.name,
            sw_version=coordinator.mill_data_connection.version,
        )
        self._update_attr()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self.coordinator.mill_data_connection.set_target_temperature(
            int(temperature)
        )
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr()
        self.async_write_ha_state()

    @callback
    def _update_attr(self) -> None:
        data = self.coordinator.data
        self._attr_target_temperature = data["set_temperature"]
        self._attr_current_temperature = data["ambient_temperature"]

        if data["current_power"] > 0:
            self._attr_hvac_action = CURRENT_HVAC_HEAT
        else:
            self._attr_hvac_action = CURRENT_HVAC_IDLE
