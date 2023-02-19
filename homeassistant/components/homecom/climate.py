"""Support for air conditioner units by Bosch HomeCom."""
import asyncio
import logging

from aiohttp.client_exceptions import ClientResponseError
from homecom.air_conditioner import AcControl, AirConditioner, OperationMode

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Hub
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure and add the air conditioners."""

    hub = hass.data[DOMAIN][config_entry.entry_id]
    try:
        acs = await hub.get_acs()
        async_add_entities((HomecomClimate(ac, hub) for ac in acs), True)
    except asyncio.TimeoutError as ex:
        raise ConfigEntryNotReady("Timed out while connecting to") from ex


class HomecomClimate(ClimateEntity):
    """Defines a Homecom climate entity."""

    _LOGGER = logging.getLogger(__name__)

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.HEAT,
        HVACMode.OFF,
    ]

    def __init__(self, air_conditioner: AirConditioner, hub: Hub) -> None:
        """Initialize."""

        self._climate = air_conditioner
        self._hub = hub
        self._attr_unique_id = str(air_conditioner.id)
        self._attr_name = f"Air Conditioner {air_conditioner.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(air_conditioner.id))},
            manufacturer="Bosch",
            name=self.name,
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._climate.room_temperature

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current hvac mode."""

        is_on = self._climate.is_on
        self._LOGGER.debug("HomecomClimate is %s", is_on)
        if is_on == AcControl.OFF:
            return HVACMode.OFF
        if self._climate.operation_mode == OperationMode.AUTO:
            return HVACMode.AUTO
        if self._climate.operation_mode == OperationMode.COOL:
            return HVACMode.COOL
        if self._climate.operation_mode == OperationMode.DRY:
            return HVACMode.DRY
        if self._climate.operation_mode == OperationMode.HEAT:
            return HVACMode.HEAT
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""

        return self._climate.target_temperature

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""

        await self._climate.async_set_target_temperature(kwargs.get(ATTR_TEMPERATURE))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        if hvac_mode == HVACMode.OFF:
            return await self._climate.async_set_ac_control(AcControl.OFF)

        await self._climate.async_set_ac_control(AcControl.ON)
        if hvac_mode == HVACMode.AUTO:
            await self._climate.async_set_operation_mode(OperationMode.AUTO)
        if hvac_mode == HVACMode.COOL:
            await self._climate.async_set_operation_mode(OperationMode.COOL)
        if hvac_mode == HVACMode.DRY:
            await self._climate.async_set_operation_mode(OperationMode.DRY)
        if hvac_mode == HVACMode.HEAT:
            await self._climate.async_set_operation_mode(OperationMode.HEAT)
        return None

    async def async_update(self) -> None:
        """Update the model."""

        try:
            self._climate = await self._hub.get_ac(self._attr_unique_id)
        except ClientResponseError:
            self._LOGGER.warning("Unable to update entity %s", self.entity_id)
