"""Platform for Mazda climate integration."""
from typing import Any

from pymazda import Client as MazdaAPIClient

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.temperature import convert as convert_temperature

from . import MazdaEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DATA_REGION, DOMAIN

PRESET_DEFROSTER_OFF = "Defroster Off"
PRESET_DEFROSTER_FRONT = "Front Defroster"
PRESET_DEFROSTER_REAR = "Rear Defroster"
PRESET_DEFROSTER_FRONT_AND_REAR = "Front and Rear Defroster"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    client = entry_data[DATA_CLIENT]
    coordinator = entry_data[DATA_COORDINATOR]
    region = entry_data[DATA_REGION]

    async_add_entities(
        MazdaClimateEntity(client, coordinator, index, region)
        for index, data in enumerate(coordinator.data)
        if data["isElectric"]
    )


class MazdaClimateEntity(MazdaEntity, ClimateEntity):
    """Class for the climate entity."""

    _attr_name = "Climate"
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_hvac_modes = [HVACMode.HEAT_COOL, HVACMode.OFF]
    _attr_preset_modes = [
        PRESET_DEFROSTER_OFF,
        PRESET_DEFROSTER_FRONT,
        PRESET_DEFROSTER_REAR,
        PRESET_DEFROSTER_FRONT_AND_REAR,
    ]

    def __init__(
        self,
        client: MazdaAPIClient,
        coordinator: DataUpdateCoordinator,
        index: int,
        region: str,
    ) -> None:
        """Initialize Mazda climate entity."""
        super().__init__(client, coordinator, index)

        self.region = region
        self._attr_unique_id = self.vin

        if self.data["hvacSetting"]["temperatureUnit"] == "F":
            self._attr_precision = PRECISION_WHOLE
            self._attr_temperature_unit = TEMP_FAHRENHEIT
            self._attr_min_temp = 61.0
            self._attr_max_temp = 83.0
        else:
            self._attr_precision = PRECISION_HALVES
            self._attr_temperature_unit = TEMP_CELSIUS
            if region == "MJO":
                self._attr_min_temp = 18.5
                self._attr_max_temp = 31.5
            else:
                self._attr_min_temp = 15.5
                self._attr_max_temp = 28.5

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Perform an initial update of the state.
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator data updates."""
        # Update the HVAC mode
        hvac_on = self.client.get_assumed_hvac_mode(self.vehicle_id)
        self._attr_hvac_mode = HVACMode.HEAT_COOL if hvac_on else HVACMode.OFF

        # Update the target temperature
        hvac_setting = self.client.get_assumed_hvac_setting(self.vehicle_id)
        self._attr_target_temperature = hvac_setting.get("temperature")

        # Update the current temperature
        current_temperature_celsius = self.data["evStatus"]["hvacInfo"][
            "interiorTemperatureCelsius"
        ]
        if self.data["hvacSetting"]["temperatureUnit"] == "F":
            self._attr_current_temperature = convert_temperature(
                current_temperature_celsius, TEMP_CELSIUS, TEMP_FAHRENHEIT
            )
        else:
            self._attr_current_temperature = current_temperature_celsius

        # Update the preset mode based on the state of the front and rear defrosters
        front_defroster = hvac_setting.get("frontDefroster")
        rear_defroster = hvac_setting.get("rearDefroster")
        if front_defroster and rear_defroster:
            self._attr_preset_mode = PRESET_DEFROSTER_FRONT_AND_REAR
        elif front_defroster:
            self._attr_preset_mode = PRESET_DEFROSTER_FRONT
        elif rear_defroster:
            self._attr_preset_mode = PRESET_DEFROSTER_REAR
        else:
            self._attr_preset_mode = PRESET_DEFROSTER_OFF

        super()._handle_coordinator_update()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set a new HVAC mode."""
        if hvac_mode == HVACMode.HEAT_COOL:
            await self.client.turn_on_hvac(self.vehicle_id)
        elif hvac_mode == HVACMode.OFF:
            await self.client.turn_off_hvac(self.vehicle_id)

        self._handle_coordinator_update()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            precision = self.precision
            rounded_temperature = round(temperature / precision) * precision

            await self.client.set_hvac_setting(
                self.vehicle_id,
                rounded_temperature,
                self.data["hvacSetting"]["temperatureUnit"],
                self._attr_preset_mode
                in [
                    PRESET_DEFROSTER_FRONT_AND_REAR,
                    PRESET_DEFROSTER_FRONT,
                ],
                self._attr_preset_mode
                in [
                    PRESET_DEFROSTER_FRONT_AND_REAR,
                    PRESET_DEFROSTER_REAR,
                ],
            )

            self._handle_coordinator_update()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Turn on/off the front/rear defrosters according to the chosen preset mode."""
        front_defroster = preset_mode in [
            PRESET_DEFROSTER_FRONT_AND_REAR,
            PRESET_DEFROSTER_FRONT,
        ]
        rear_defroster = preset_mode in [
            PRESET_DEFROSTER_FRONT_AND_REAR,
            PRESET_DEFROSTER_REAR,
        ]

        await self.client.set_hvac_setting(
            self.vehicle_id,
            self._attr_target_temperature,
            self.data["hvacSetting"]["temperatureUnit"],
            front_defroster,
            rear_defroster,
        )

        self._handle_coordinator_update()
