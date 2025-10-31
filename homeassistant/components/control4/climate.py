"""Platform for Control4 Climate/Thermostat."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pyControl4.climate import C4Climate
from pyControl4.error_handling import C4Exception

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import Control4ConfigEntry, Control4RuntimeData, get_items_of_category
from .const import CONTROL4_ENTITY_TYPE
from .director_utils import update_variables_for_config_entry
from .entity import Control4Entity

_LOGGER = logging.getLogger(__name__)

CONTROL4_CATEGORY = "comfort"

# Control4 variable names
CONTROL4_HVAC_STATE = "HVAC_STATE"
CONTROL4_HVAC_MODE = "HVAC_MODE"
CONTROL4_CURRENT_TEMPERATURE = "TEMPERATURE_F"
CONTROL4_HUMIDITY = "HUMIDITY"
CONTROL4_COOL_SETPOINT = "COOL_SETPOINT_F"
CONTROL4_HEAT_SETPOINT = "HEAT_SETPOINT_F"

VARIABLES_OF_INTEREST = {
    CONTROL4_HVAC_STATE,
    CONTROL4_HVAC_MODE,
    CONTROL4_CURRENT_TEMPERATURE,
    CONTROL4_HUMIDITY,
    CONTROL4_COOL_SETPOINT,
    CONTROL4_HEAT_SETPOINT,
}

# Map Control4 HVAC modes to Home Assistant
C4_TO_HA_HVAC_MODE = {
    "Off": HVACMode.OFF,
    "Cool": HVACMode.COOL,
    "Heat": HVACMode.HEAT,
    "Auto": HVACMode.HEAT_COOL,
}

HA_TO_C4_HVAC_MODE = {v: k for k, v in C4_TO_HA_HVAC_MODE.items()}

# Map Control4 HVAC state to Home Assistant HVAC action
C4_TO_HA_HVAC_ACTION = {
    "heating": HVACAction.HEATING,
    "cooling": HVACAction.COOLING,
    "idle": HVACAction.IDLE,
    "off": HVACAction.OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Control4ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Control4 thermostats from a config entry."""
    runtime_data = entry.runtime_data

    async def async_update_data() -> dict[int, dict[str, Any]]:
        """Fetch data from Control4 director for thermostats."""
        try:
            return await update_variables_for_config_entry(
                hass, entry, VARIABLES_OF_INTEREST
            )
        except C4Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator[dict[int, dict[str, Any]]](
        hass,
        _LOGGER,
        name="climate",
        update_method=async_update_data,
        update_interval=timedelta(seconds=runtime_data.scan_interval),
        config_entry=entry,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    items_of_category = await get_items_of_category(hass, entry, CONTROL4_CATEGORY)
    entity_list = []
    for item in items_of_category:
        try:
            if item["type"] == CONTROL4_ENTITY_TYPE:
                item_name = item["name"]
                item_id = item["id"]
                item_parent_id = item["parentId"]
                item_manufacturer = None
                item_device_name = None
                item_model = None

                for parent_item in items_of_category:
                    if parent_item["id"] == item_parent_id:
                        item_manufacturer = parent_item.get("manufacturer")
                        item_device_name = parent_item.get("roomName")
                        item_model = parent_item.get("model")
            else:
                continue
        except KeyError:
            _LOGGER.exception(
                "Unknown device properties received from Control4: %s",
                item,
            )
            continue

        # Skip if we don't have data for this thermostat
        if item_id not in coordinator.data:
            _LOGGER.warning(
                "Couldn't get climate state data for %s (ID: %s), skipping setup",
                item_name,
                item_id,
            )
            continue

        entity_list.append(
            Control4Climate(
                runtime_data,
                coordinator,
                item_name,
                item_id,
                item_device_name,
                item_manufacturer,
                item_model,
                item_parent_id,
            )
        )

    async_add_entities(entity_list)


class Control4Climate(Control4Entity, ClimateEntity):
    """Control4 climate entity."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.HEAT_COOL]

    def __init__(
        self,
        runtime_data: Control4RuntimeData,
        coordinator: DataUpdateCoordinator[dict[int, dict[str, Any]]],
        name: str,
        idx: int,
        device_name: str | None,
        device_manufacturer: str | None,
        device_model: str | None,
        device_id: int,
    ) -> None:
        """Initialize Control4 climate entity."""
        super().__init__(
            runtime_data,
            coordinator,
            name,
            idx,
            device_name,
            device_manufacturer,
            device_model,
            device_id,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._thermostat_data is not None

    def _create_api_object(self) -> C4Climate:
        """Create a pyControl4 device object.

        This exists so the director token used is always the latest one, without needing to re-init the entire entity.
        """
        return C4Climate(self.runtime_data.director, self._idx)

    @property
    def _thermostat_data(self) -> dict[str, Any] | None:
        """Return the thermostat data from the coordinator."""
        return self.coordinator.data.get(self._idx)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        data = self._thermostat_data
        if data is None:
            return None
        return data.get(CONTROL4_CURRENT_TEMPERATURE)

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        data = self._thermostat_data
        if data is None:
            return None
        humidity = data.get(CONTROL4_HUMIDITY)
        return int(humidity) if humidity is not None else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        data = self._thermostat_data
        if data is None:
            return HVACMode.OFF
        c4_mode = data.get(CONTROL4_HVAC_MODE) or ""
        return C4_TO_HA_HVAC_MODE.get(c4_mode, HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action."""
        data = self._thermostat_data
        if data is None:
            return None
        c4_state = data.get(CONTROL4_HVAC_STATE)
        if c4_state is None:
            return None
        # Convert state to lowercase for mapping
        return C4_TO_HA_HVAC_ACTION.get(str(c4_state).lower())

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        data = self._thermostat_data
        if data is None:
            return None
        hvac_mode = self.hvac_mode
        if hvac_mode == HVACMode.COOL:
            return data.get(CONTROL4_COOL_SETPOINT)
        if hvac_mode == HVACMode.HEAT:
            return data.get(CONTROL4_HEAT_SETPOINT)
        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the high target temperature for auto mode."""
        data = self._thermostat_data
        if data is None:
            return None
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return data.get(CONTROL4_COOL_SETPOINT)
        return None

    @property
    def target_temperature_low(self) -> float | None:
        """Return the low target temperature for auto mode."""
        data = self._thermostat_data
        if data is None:
            return None
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return data.get(CONTROL4_HEAT_SETPOINT)
        return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        c4_hvac_mode = HA_TO_C4_HVAC_MODE[hvac_mode]
        c4_climate = self._create_api_object()
        await c4_climate.setHvacMode(c4_hvac_mode)
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        c4_climate = self._create_api_object()
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp = kwargs.get(ATTR_TEMPERATURE)

        # Handle temperature range for auto mode
        if self.hvac_mode == HVACMode.HEAT_COOL:
            if low_temp is not None:
                await c4_climate.setHeatSetpointF(low_temp)
            if high_temp is not None:
                await c4_climate.setCoolSetpointF(high_temp)
        # Handle single temperature setpoint
        elif temp is not None:
            if self.hvac_mode == HVACMode.COOL:
                await c4_climate.setCoolSetpointF(temp)
            elif self.hvac_mode == HVACMode.HEAT:
                await c4_climate.setHeatSetpointF(temp)

        await self.coordinator.async_request_refresh()
