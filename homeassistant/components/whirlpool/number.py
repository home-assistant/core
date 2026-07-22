"""Number platform for the Whirlpool Appliances integration."""

from typing import override

from whirlpool.oven import Cavity as OvenCavity, CookMode, Oven

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WhirlpoolConfigEntry
from .const import DOMAIN
from .entity import WhirlpoolOvenEntity

PARALLEL_UPDATES = 1

# Oven target temperatures are handled in Celsius. The appliance accepts
# tenth-of-a-degree values, so a 1-degree step gives fine manual control while
# automations can still set any value Home Assistant passes through.
OVEN_MIN_TEMP = 30
OVEN_MAX_TEMP = 290
OVEN_TEMP_STEP = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WhirlpoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number platform."""
    appliances_manager = config_entry.runtime_data
    async_add_entities(
        WhirlpoolOvenTargetTemperature(oven, cavity)
        for oven in appliances_manager.ovens
        for cavity in (OvenCavity.Upper, OvenCavity.Lower)
        if oven.get_oven_cavity_exists(cavity)
    )


class WhirlpoolOvenTargetTemperature(WhirlpoolOvenEntity, NumberEntity):
    """Settable target temperature for an oven cavity."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = OVEN_MIN_TEMP
    _attr_native_max_value = OVEN_MAX_TEMP
    _attr_native_step = OVEN_TEMP_STEP

    def __init__(self, appliance: Oven, cavity: OvenCavity) -> None:
        """Initialize the oven target temperature number."""
        super().__init__(
            appliance, cavity, "oven_target_temperature", "-target_temperature"
        )

    @override
    @property
    def native_value(self) -> float | None:
        """Return the current target temperature."""
        return self._appliance.get_target_temp(self.cavity)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set a new target temperature, keeping the current cook mode."""
        mode = self._appliance.get_cook_mode(self.cavity)
        if mode is None or mode == CookMode.Standby:
            mode = CookMode.Bake
        try:
            WhirlpoolOvenTargetTemperature._check_service_request(
                await self._appliance.set_cook(
                    target_temp=value, mode=mode, cavity=self.cavity
                )
            )
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_value_set",
            ) from err
