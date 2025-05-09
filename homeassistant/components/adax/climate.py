"""Support for Adax wifi-enabled home heaters."""

from __future__ import annotations

from typing import Any, cast

from adax import Adax
from adax_local import Adax as AdaxLocal

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_UNIQUE_ID,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AdaxConfigEntry
from .const import CONNECTION_TYPE, DOMAIN, LOCAL
from .coordinator import AdaxCloudCoordinator, AdaxLocalCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdaxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Adax thermostat with config flow."""
    if entry.data.get(CONNECTION_TYPE) == LOCAL:
        local_coordinator = cast(AdaxLocalCoordinator, entry.runtime_data)
        async_add_entities(
            [LocalAdaxDevice(local_coordinator, entry.data[CONF_UNIQUE_ID])],
        )
    else:
        cloud_coordinator = cast(AdaxCloudCoordinator, entry.runtime_data)
        async_add_entities(
            AdaxDevice(cloud_coordinator, device_id)
            for device_id in cloud_coordinator.data
        )


class AdaxDevice(CoordinatorEntity[AdaxCloudCoordinator], ClimateEntity):
    """Representation of a heater."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_max_temp = 35
    _attr_min_temp = 5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: AdaxCloudCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the heater."""
        super().__init__(coordinator)
        self._adax_data_handler: Adax = coordinator.adax_data_handler
        self._device_id = device_id

        self._attr_name = self.room["name"]
        self._attr_unique_id = f"{self.room['homeId']}_{self._device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            # Instead of setting the device name to the entity name, adax
            # should be updated to set has_entity_name = True, and set the entity
            # name to None
            name=cast(str | None, self.name),
            manufacturer="Adax",
        )
        self._apply_data(self.room)

    @property
    def available(self) -> bool:
        """Whether the entity is available or not."""
        return super().available and self._device_id in self.coordinator.data

    @property
    def room(self) -> dict[str, Any]:
        """Gets the data for this particular device."""
        return self.coordinator.data[self._device_id]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        if hvac_mode == HVACMode.HEAT:
            temperature = max(self.min_temp, self.target_temperature or self.min_temp)
            await self._adax_data_handler.set_room_target_temperature(
                self._device_id, temperature, True
            )
        elif hvac_mode == HVACMode.OFF:
            await self._adax_data_handler.set_room_target_temperature(
                self._device_id, self.min_temp, False
            )
        else:
            return

        # Request data refresh from source to verify that update was successful
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        if temperature == 0:
            # Temp value of 0 should be treated as a 'turn-off' command
            await self.async_turn_off()
        else:
            await self._adax_data_handler.set_room_target_temperature(
                self._device_id, temperature, True
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if room := self.room:
            self._apply_data(room)
        super()._handle_coordinator_update()

    def _apply_data(self, room: dict[str, Any]) -> None:
        """Update the appropriate attributues based on received data."""
        self._attr_current_temperature = room.get("temperature")
        self._attr_target_temperature = room.get("targetTemperature")
        if room["heatingEnabled"]:
            self._attr_hvac_mode = HVACMode.HEAT
            self._attr_icon = "mdi:radiator"
        else:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_icon = "mdi:radiator-off"


class LocalAdaxDevice(CoordinatorEntity[AdaxLocalCoordinator], ClimateEntity):
    """Representation of a heater."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_hvac_mode = HVACMode.OFF
    _attr_icon = "mdi:radiator-off"
    _attr_max_temp = 35
    _attr_min_temp = 5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: AdaxLocalCoordinator, unique_id: str) -> None:
        """Initialize the heater."""
        super().__init__(coordinator)
        self._adax_data_handler: AdaxLocal = coordinator.adax_data_handler
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Adax",
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        if hvac_mode == HVACMode.HEAT:
            temperature = self._attr_target_temperature or self._attr_min_temp
            await self._adax_data_handler.set_target_temperature(temperature)
        elif hvac_mode == HVACMode.OFF:
            await self._adax_data_handler.set_target_temperature(0)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._adax_data_handler.set_target_temperature(temperature)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if data := self.coordinator.data:
            self._attr_current_temperature = data["current_temperature"]
            self._attr_available = self._attr_current_temperature is not None
            if (target_temp := data["target_temperature"]) == 0:
                self._attr_hvac_mode = HVACMode.OFF
                self._attr_icon = "mdi:radiator-off"
                if target_temp == 0:
                    self._attr_target_temperature = self._attr_min_temp
            else:
                self._attr_hvac_mode = HVACMode.HEAT
                self._attr_icon = "mdi:radiator"
                self._attr_target_temperature = target_temp

        super()._handle_coordinator_update()
