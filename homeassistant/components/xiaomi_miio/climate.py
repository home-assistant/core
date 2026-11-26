"""Support for Xiaomi Smart Space Heaters."""

from functools import partial
from typing import Any, override

from miio import DeviceException, HeaterMiot
from miio.heater_miot import HEATER_PROPERTIES, HeaterMiotStatus

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import XiaomiCoordinatedMiioEntity
from .typing import XiaomiMiioConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: XiaomiMiioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the heater from a config entry."""
    unique_id = config_entry.unique_id
    device = config_entry.runtime_data.device
    assert unique_id is not None
    assert isinstance(device, HeaterMiot)
    async_add_entities(
        [
            XiaomiHeater(
                device,
                config_entry,
                unique_id,
                config_entry.runtime_data.device_coordinator,
            )
        ]
    )


class XiaomiHeater(
    XiaomiCoordinatedMiioEntity[DataUpdateCoordinator[HeaterMiotStatus]],
    ClimateEntity,
):
    """Representation of a Xiaomi Smart Space Heater."""

    _attr_name = None
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_target_temperature_step = 1
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _device: HeaterMiot

    def __init__(
        self,
        device: HeaterMiot,
        entry: XiaomiMiioConfigEntry,
        unique_id: str,
        coordinator: DataUpdateCoordinator[HeaterMiotStatus],
    ) -> None:
        """Initialize the heater."""
        super().__init__(device, entry, unique_id, coordinator)
        self._attr_min_temp, self._attr_max_temp = HEATER_PROPERTIES[self._model][
            "temperature_range"
        ]
        self._update_attributes()

    @callback
    def _update_attributes(self) -> None:
        """Update the entity attributes from the coordinator data."""
        status = self.coordinator.data
        self._attr_hvac_mode = HVACMode.HEAT if status.is_on else HVACMode.OFF
        self._attr_native_target_temperature = status.target_temperature
        self._attr_native_current_temperature = status.temperature

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        super()._handle_coordinator_update()

    async def _async_send_command(self, func, *args: Any) -> None:
        """Send a command to the heater and refresh its state."""
        try:
            await self.hass.async_add_executor_job(partial(func, *args))
        except DeviceException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="heater_command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        await self._async_send_command(
            self._device.set_target_temperature, int(kwargs[ATTR_TEMPERATURE])
        )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the heater on or off."""
        if hvac_mode == HVACMode.HEAT:
            await self._async_send_command(self._device.on)
        else:
            await self._async_send_command(self._device.off)
