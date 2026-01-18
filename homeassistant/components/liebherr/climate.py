"""Climate platform for Liebherr integration."""

from __future__ import annotations

from typing import Any

from pyliebherrhomeapi import (
    LiebherrBadRequestError,
    LiebherrConnectionError,
    TemperatureUnit,
)

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LiebherrCoordinator
from .entity import LiebherrZoneEntity
from .models import LiebherrConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Liebherr climate entities."""
    coordinator = entry.runtime_data.coordinator
    entities: list[LiebherrClimateEntity] = []

    for device_id, device_state in coordinator.data.items():
        # Get all temperature controls for this device
        temp_controls = device_state.get_temperature_controls()

        entities.extend(
            LiebherrClimateEntity(
                coordinator=coordinator,
                device_id=device_id,
                zone_id=temp_control.zone_id,
            )
            for temp_control in temp_controls
        )

    async_add_entities(entities)


class LiebherrClimateEntity(LiebherrZoneEntity, ClimateEntity):
    """Representation of a Liebherr climate entity."""

    _attr_hvac_modes = [HVACMode.COOL]
    _attr_hvac_mode = HVACMode.COOL
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = 1.0
    _attr_precision = PRECISION_WHOLE

    def __init__(
        self,
        coordinator: LiebherrCoordinator,
        device_id: str,
        zone_id: int,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, device_id, zone_id)

        # Set unique ID based on device and zone
        self._attr_unique_id = f"{device_id}-climate-{zone_id}"

        # If device has only one zone, use model name instead of zone name
        device_state = coordinator.data[device_id]
        temp_controls = device_state.get_temperature_controls()
        if len(temp_controls) == 1:
            self._attr_name = None
        else:
            # Set translation key based on zone position for multi-zone devices
            self._attr_translation_key = self._get_zone_translation_key()

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        control = self.temperature_control
        if control and control.unit == TemperatureUnit.FAHRENHEIT:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        control = self.temperature_control
        if control and control.value is not None:
            return float(control.value)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        control = self.temperature_control
        if control and control.target is not None:
            return float(control.target)
        return None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        control = self.temperature_control
        if control and control.min is not None:
            return float(control.min)
        # Default minimum for refrigerators
        return -30.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        control = self.temperature_control
        if control and control.max is not None:
            return float(control.max)
        # Default maximum for refrigerators
        return 15.0

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.temperature_control is not None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        control = self.temperature_control
        assert control is not None

        try:
            await self.coordinator.client.set_temperature(
                device_id=self._device_id,
                zone_id=self._zone_id,
                target=int(temperature),
                unit=control.unit
                if isinstance(control.unit, TemperatureUnit)
                else TemperatureUnit.CELSIUS,
            )
        except LiebherrBadRequestError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_temperature",
            ) from err
        except LiebherrConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_failed",
            ) from err

        # Request immediate update
        await self.coordinator.async_request_refresh()
