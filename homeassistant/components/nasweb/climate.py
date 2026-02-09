"""Platform for NASweb thermostat."""

from __future__ import annotations

import time
from typing import Any

from webio_api import Thermostat as NASwebThermostat
from webio_api.const import KEY_THERMOSTAT

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    UnitOfTemperature,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    BaseCoordinatorEntity,
    BaseDataUpdateCoordinatorProtocol,
)

from . import NASwebConfigEntry
from .const import DOMAIN, STATUS_UPDATE_MAX_TIME_INTERVAL

CLIMATE_TRANSLATION_KEY = "thermostat"


async def async_setup_entry(
    hass: HomeAssistant,
    config: NASwebConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Climate platform."""
    coordinator = config.runtime_data
    nasweb_thermostat: NASwebThermostat = coordinator.data[KEY_THERMOSTAT]
    climate = Thermostat(coordinator, nasweb_thermostat)
    async_add_entities([climate])


class Thermostat(ClimateEntity, BaseCoordinatorEntity):
    """Entity representing NASweb thermostat."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_has_entity_name = True
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.FAN_ONLY,
    ]
    _attr_max_temp = 50
    _attr_min_temp = -50
    _attr_precision = 1.0
    _attr_should_poll = False
    _attr_supported_features = ClimateEntityFeature(
        ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )
    _attr_target_temperature_step = 1.0
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = CLIMATE_TRANSLATION_KEY

    def __init__(
        self,
        coordinator: BaseDataUpdateCoordinatorProtocol,
        nasweb_thermostat: NASwebThermostat,
    ) -> None:
        """Initialize Thermostat."""
        super().__init__(coordinator)
        self._thermostat = nasweb_thermostat
        self._attr_available = False
        self._attr_name = nasweb_thermostat.name
        self._attr_unique_id = f"{DOMAIN}.{self._thermostat.webio_serial}.thermostat"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._thermostat.webio_serial)}
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    def _set_attr_available(
        self, entity_last_update: float, available: bool | None
    ) -> None:
        if (
            self.coordinator.last_update is None
            or time.time() - entity_last_update >= STATUS_UPDATE_MAX_TIME_INTERVAL
        ):
            self._attr_available = False
        else:
            self._attr_available = available if available is not None else False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_current_temperature = self._thermostat.current_temp
        self._attr_target_temperature_low = self._thermostat.temp_target_min
        self._attr_target_temperature_high = self._thermostat.temp_target_max
        self._attr_hvac_mode = self._get_current_hvac_mode()
        self._attr_hvac_action = self._get_current_action()
        self._attr_name = self._thermostat.name or None
        self._set_attr_available(
            self._thermostat.last_update, self._thermostat.available
        )
        self.async_write_ha_state()

    def _get_current_hvac_mode(self) -> HVACMode:
        have_cooling = self._thermostat.enabled_above_output
        have_heating = self._thermostat.enabled_below_output
        if have_cooling and have_heating:
            return HVACMode.HEAT_COOL
        if have_cooling:
            return HVACMode.COOL
        if have_heating:
            return HVACMode.HEAT
        if self._thermostat.enabled_inrange_output:
            return HVACMode.FAN_ONLY
        return HVACMode.OFF

    def _get_current_action(self) -> HVACAction:
        if self._thermostat.current_temp is None:
            return HVACAction.OFF
        if (
            self._thermostat.temp_target_min is not None
            and self._thermostat.current_temp < self._thermostat.temp_target_min
            and self._thermostat.enabled_below_output
        ):
            return HVACAction.HEATING
        if (
            self._thermostat.temp_target_max is not None
            and self._thermostat.current_temp > self._thermostat.temp_target_max
            and self._thermostat.enabled_above_output
        ):
            return HVACAction.COOLING
        if (
            self._thermostat.temp_target_min is not None
            and self._thermostat.temp_target_max is not None
            and self._thermostat.current_temp >= self._thermostat.temp_target_min
            and self._thermostat.current_temp <= self._thermostat.temp_target_max
            and self._thermostat.enabled_inrange_output
        ):
            return HVACAction.FAN
        return HVACAction.IDLE

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        Scheduling updates is not necessary, the coordinator takes care of updates via push notifications.
        """

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVACMode for Thermostat."""
        await self._thermostat.set_hvac_mode(hvac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set temperature range for Thermostat."""
        await self._thermostat.set_temperature(
            kwargs["target_temp_low"], kwargs["target_temp_high"]
        )
