"""Number platform for Tessie integration."""
from __future__ import annotations

from tessie_api import set_charge_limit, set_charging_amps, set_speed_limit

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    PRECISION_WHOLE,
    UnitOfElectricCurrent,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TessieDataUpdateCoordinator
from .entity import TessieEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tessie sensor platform from a config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        EntityClass(coordinator)
        for EntityClass in (
            TessieChargeLimitSocNumberEntity,
            TessieSpeedLimitModeNumberEntity,
            TessieCurrentChargeNumberEntity,
        )
        for coordinator in coordinators
    )


class TessieCurrentChargeNumberEntity(TessieEntity, NumberEntity):
    """Number entity for current charge."""

    _attr_native_step = PRECISION_WHOLE
    _attr_native_min_value = 0
    _attr_native_max_value = 32
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_device_class = NumberDeviceClass.CURRENT

    def __init__(
        self,
        coordinator: TessieDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "charge_state_charge_current_request")

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        return self._value

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self.get(
            "charge_state_charge_current_request_max", self._attr_native_max_value
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.run(set_charging_amps, amps=value)
        self.set((self.key, value))


class TessieChargeLimitSocNumberEntity(TessieEntity, NumberEntity):
    """Number entity for charge limit soc."""

    _attr_native_step = PRECISION_WHOLE
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = NumberDeviceClass.BATTERY

    def __init__(
        self,
        coordinator: TessieDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "charge_state_charge_limit_soc")

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        return self._value

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return self.get(
            "charge_state_charge_limit_soc_min", self._attr_native_min_value
        )

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self.get(
            "charge_state_charge_limit_soc_max", self._attr_native_max_value
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.run(set_charge_limit, percent=value)
        self.set((self.key, value))


class TessieSpeedLimitModeNumberEntity(TessieEntity, NumberEntity):
    """Number entity for speed limit mode."""

    _attr_native_step = PRECISION_WHOLE
    _attr_native_min_value = 50
    _attr_native_max_value = 120
    _attr_native_unit_of_measurement = UnitOfSpeed.MILES_PER_HOUR
    _attr_device_class = NumberDeviceClass.SPEED
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: TessieDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, "vehicle_state_speed_limit_mode_current_limit_mph"
        )

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        return self._value

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return self.get(
            "vehicle_state_speed_limit_mode_min_limit_mph", self._attr_native_min_value
        )

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self.get(
            "vehicle_state_speed_limit_mode_max_limit_mph", self._attr_native_max_value
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.run(set_speed_limit, mph=value)
        self.set((self.key, value))
