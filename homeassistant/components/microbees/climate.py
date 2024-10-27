"""Climate integration microBees."""

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MicroBeesUpdateCoordinator
from .entity import MicroBeesActuatorEntity

CLIMATE_PRODUCT_IDS = {
    76,  # Thermostat,
    78,  # Thermovalve,
}
THERMOSTAT_SENSOR_ID = 762
THERMOVALVE_SENSOR_ID = 782


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the microBees climate platform."""
    coordinator: MicroBeesUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ].coordinator
    async_add_entities(
        MBClimate(
            coordinator,
            bee_id,
            bee.actuators[0].id,
            next(
                sensor.id
                for sensor in bee.sensors
                if sensor.deviceID
                == (
                    THERMOSTAT_SENSOR_ID
                    if bee.productID == 76
                    else THERMOVALVE_SENSOR_ID
                )
            ),
        )
        for bee_id, bee in coordinator.data.bees.items()
        if bee.productID in CLIMATE_PRODUCT_IDS
    )


class MBClimate(MicroBeesActuatorEntity, ClimateEntity):
    """Representation of a microBees climate."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_fan_modes = None
    _attr_min_temp = 15
    _attr_max_temp = 35
    _attr_name = None

    def __init__(
        self,
        coordinator: MicroBeesUpdateCoordinator,
        bee_id: int,
        actuator_id: int,
        sensor_id: int,
    ) -> None:
        """Initialize the microBees climate."""
        super().__init__(coordinator, bee_id, actuator_id)
        self.sensor_id = sensor_id

    @property
    def current_temperature(self) -> float | None:
        """Return the sensor temperature."""
        return self.coordinator.data.sensors[self.sensor_id].value

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current hvac operation i.e. heat, cool mode."""
        if self.actuator.value == 1:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def target_temperature(self) -> float | None:
        """Return the current target temperature."""
        return self.bee.instanceData.targetTemp

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        send_command = await self.coordinator.microbees.sendCommand(
            self.actuator_id, self.actuator.value, temperature=temperature
        )

        if not send_command:
            raise HomeAssistantError(f"Failed to set temperature {self.name}")

        self.bee.instanceData.targetTemp = temperature
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode, **kwargs: Any) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            return await self.async_turn_off()
        return await self.async_turn_on()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the climate."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        send_command = await self.coordinator.microbees.sendCommand(
            self.actuator_id, 1, temperature=temperature
        )

        if not send_command:
            raise HomeAssistantError(f"Failed to set temperature {self.name}")

        self.actuator.value = 1
        self._attr_hvac_mode = HVACMode.HEAT
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the climate."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        send_command = await self.coordinator.microbees.sendCommand(
            self.actuator_id, 0, temperature=temperature
        )

        if not send_command:
            raise HomeAssistantError(f"Failed to set temperature {self.name}")

        self.actuator.value = 0
        self._attr_hvac_mode = HVACMode.OFF
        self.async_write_ha_state()
