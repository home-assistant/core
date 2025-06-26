"""Support for mill wifi-enabled home heaters."""

from typing import Any

import mill
from mill_local import OperationMode
import voluptuous as vol

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_IP_ADDRESS,
    CONF_USERNAME,
    PRECISION_TENTHS,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_AWAY_TEMP,
    ATTR_COMFORT_TEMP,
    ATTR_ROOM_NAME,
    ATTR_SLEEP_TEMP,
    CLOUD,
    CONNECTION_TYPE,
    DOMAIN,
    LOCAL,
    MANUFACTURER,
    MAX_TEMP,
    MIN_TEMP,
    SERVICE_SET_ROOM_TEMP,
)
from .coordinator import MillDataUpdateCoordinator
from .entity import MillBaseEntity

SET_ROOM_TEMP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ROOM_NAME): cv.string,
        vol.Optional(ATTR_AWAY_TEMP): cv.positive_int,
        vol.Optional(ATTR_COMFORT_TEMP): cv.positive_int,
        vol.Optional(ATTR_SLEEP_TEMP): cv.positive_int,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Mill climate."""
    if entry.data.get(CONNECTION_TYPE) == LOCAL:
        mill_data_coordinator = hass.data[DOMAIN][LOCAL][entry.data[CONF_IP_ADDRESS]]
        async_add_entities([LocalMillHeater(mill_data_coordinator)])
        return

    mill_data_coordinator = hass.data[DOMAIN][CLOUD][entry.data[CONF_USERNAME]]

    entities = [
        MillHeater(mill_data_coordinator, mill_device)
        for mill_device in mill_data_coordinator.data.values()
        if isinstance(mill_device, mill.Heater)
    ]
    async_add_entities(entities)

    async def set_room_temp(service: ServiceCall) -> None:
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


class MillHeater(MillBaseEntity, ClimateEntity):
    """Representation of a Mill Thermostat device."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_max_temp = MAX_TEMP
    _attr_min_temp = MIN_TEMP
    _attr_name = None
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = PRECISION_TENTHS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self, coordinator: MillDataUpdateCoordinator, device: mill.Heater
    ) -> None:
        """Initialize the thermostat."""
        self._attr_unique_id = device.device_id
        super().__init__(coordinator, device)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self.coordinator.mill_data_connection.set_heater_temp(
            self._id, float(temperature)
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.HEAT:
            await self.coordinator.mill_data_connection.heater_control(
                self._id, power_status=True
            )
            await self.coordinator.async_request_refresh()
        elif hvac_mode == HVACMode.OFF:
            await self.coordinator.mill_data_connection.heater_control(
                self._id, power_status=False
            )
            await self.coordinator.async_request_refresh()

    @callback
    def _update_attr(self, device: mill.Heater) -> None:
        self._available = device.available
        self._attr_extra_state_attributes = {
            "open_window": device.open_window,
            "controlled_by_tibber": device.tibber_control,
        }
        if device.room_name:
            self._attr_extra_state_attributes["room"] = device.room_name
            self._attr_extra_state_attributes["avg_room_temp"] = device.room_avg_temp
        else:
            self._attr_extra_state_attributes["room"] = "Independent device"
        self._attr_target_temperature = device.set_temp
        self._attr_current_temperature = device.current_temp
        if device.is_heating:
            self._attr_hvac_action = HVACAction.HEATING
        else:
            self._attr_hvac_action = HVACAction.IDLE
        if device.power_status:
            self._attr_hvac_mode = HVACMode.HEAT
        else:
            self._attr_hvac_mode = HVACMode.OFF


class LocalMillHeater(CoordinatorEntity[MillDataUpdateCoordinator], ClimateEntity):
    """Representation of a Mill Thermostat device."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_max_temp = MAX_TEMP
    _attr_min_temp = MIN_TEMP
    _attr_name = None
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = PRECISION_TENTHS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: MillDataUpdateCoordinator) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator)
        if mac := coordinator.mill_data_connection.mac_address:
            self._attr_unique_id = mac
            self._attr_device_info = DeviceInfo(
                connections={(CONNECTION_NETWORK_MAC, mac)},
                configuration_url=self.coordinator.mill_data_connection.url,
                manufacturer=MANUFACTURER,
                model="Generation 3",
                name=coordinator.mill_data_connection.name,
                sw_version=coordinator.mill_data_connection.version,
            )

        self._update_attr()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self.coordinator.mill_data_connection.set_target_temperature(
            float(temperature)
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.HEAT:
            await self.coordinator.mill_data_connection.set_operation_mode_control_individually()
            await self.coordinator.async_request_refresh()
        elif hvac_mode == HVACMode.OFF:
            await self.coordinator.mill_data_connection.set_operation_mode_off()
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

        if data["operation_mode"] == OperationMode.OFF.value:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
        else:
            self._attr_hvac_mode = HVACMode.HEAT
            if data["current_power"] > 0:
                self._attr_hvac_action = HVACAction.HEATING
            else:
                self._attr_hvac_action = HVACAction.IDLE
