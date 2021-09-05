"""Support for mill wifi-enabled home heaters."""
import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    FAN_ON,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_AWAY_TEMP,
    ATTR_COMFORT_TEMP,
    ATTR_ROOM_NAME,
    ATTR_SLEEP_TEMP,
    DOMAIN,
    MANUFACTURER,
    MAX_TEMP,
    MIN_TEMP,
    SERVICE_SET_ROOM_TEMP,
)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE

SET_ROOM_TEMP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ROOM_NAME): cv.string,
        vol.Optional(ATTR_AWAY_TEMP): cv.positive_int,
        vol.Optional(ATTR_COMFORT_TEMP): cv.positive_int,
        vol.Optional(ATTR_SLEEP_TEMP): cv.positive_int,
    }
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Mill climate."""

    mill_data_coordinator = hass.data[DOMAIN]

    dev = []
    for heater in mill_data_coordinator.data.values():
        dev.append(MillHeater(mill_data_coordinator, heater))
    async_add_entities(dev)

    async def set_room_temp(service):
        """Set room temp."""
        room_name = service.data.get(ATTR_ROOM_NAME)
        sleep_temp = service.data.get(ATTR_SLEEP_TEMP)
        comfort_temp = service.data.get(ATTR_COMFORT_TEMP)
        away_temp = service.data.get(ATTR_AWAY_TEMP)
        await mill_data_coordinator.mill_data_connection.set_room_temperatures_by_name(
            room_name, sleep_temp, comfort_temp, away_temp
        )

    hass.services.async_register(
        DOMAIN, SERVICE_SET_ROOM_TEMP, set_room_temp, schema=SET_ROOM_TEMP_SCHEMA
    )


class MillHeater(CoordinatorEntity, ClimateEntity):
    """Representation of a Mill Thermostat device."""

    _attr_fan_modes = [FAN_ON, HVAC_MODE_OFF]
    _attr_max_temp = MAX_TEMP
    _attr_min_temp = MIN_TEMP
    _attr_supported_features = SUPPORT_FLAGS
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(self, coordinator, heater):
        """Initialize the thermostat."""

        super().__init__(coordinator)

        self._id = heater.device_id
        self._attr_unique_id = heater.device_id
        self._attr_name = heater.name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, heater.device_id)},
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": f"generation {1 if heater.is_gen1 else 2}",
        }
        if heater.is_gen1:
            self._attr_hvac_modes = [HVAC_MODE_HEAT]
        else:
            self._attr_hvac_modes = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
        self._update_attr(heater)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.mill_data_connection.set_heater_temp(
            self._id, int(temperature)
        )
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        fan_status = 1 if fan_mode == FAN_ON else 0
        await self.coordinator.mill_data_connection.heater_control(
            self._id, fan_status=fan_status
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        heater = self.coordinator.data[self._id]

        if hvac_mode == HVAC_MODE_HEAT:
            await self.coordinator.mill_data_connection.heater_control(
                self._id, power_status=1
            )
            await self.coordinator.async_request_refresh()
        elif hvac_mode == HVAC_MODE_OFF and not heater.is_gen1:
            await self.coordinator.mill_data_connection.heater_control(
                self._id, power_status=0
            )
            await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr(self.coordinator.data[self._id])
        self.async_write_ha_state()

    @callback
    def _update_attr(self, heater):
        self._attr_available = heater.available
        self._attr_extra_state_attributes = {
            "open_window": heater.open_window,
            "heating": heater.is_heating,
            "controlled_by_tibber": heater.tibber_control,
            "heater_generation": 1 if heater.is_gen1 else 2,
        }
        if heater.room:
            self._attr_extra_state_attributes["room"] = heater.room.name
            self._attr_extra_state_attributes["avg_room_temp"] = heater.room.avg_temp
        else:
            self._attr_extra_state_attributes["room"] = "Independent device"
        self._attr_target_temperature = heater.set_temp
        self._attr_current_temperature = heater.current_temp
        self._attr_fan_mode = FAN_ON if heater.fan_status == 1 else HVAC_MODE_OFF
        if heater.is_gen1 or heater.is_heating == 1:
            self._attr_hvac_action = CURRENT_HVAC_HEAT
        else:
            self._attr_hvac_action = CURRENT_HVAC_IDLE
        if heater.is_gen1 or heater.power_status == 1:
            self._attr_hvac_mode = HVAC_MODE_HEAT
        else:
            self._attr_hvac_mode = HVAC_MODE_OFF
