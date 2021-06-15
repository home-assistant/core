"""Support for Modern Forms switches."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TIME_SECONDS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ModernFormsDataUpdateCoordinator, ModernFormsDeviceEntity
from .const import CLEAR_TIMER, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Modern Forms sensor based on a config entry."""
    coordinator: ModernFormsDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: list[ModernFormsSensor] = [
        ModernFormsFanTimerRemainingTimeSensor(entry.entry_id, coordinator),
    ]

    # Only setup light sleep timer sensor if light unit installed
    if coordinator.data.info.light_type:
        sensors.append(
            ModernFormsLightTimerRemainingTimeSensor(entry.entry_id, coordinator)
        )

    async_add_entities(sensors)


class ModernFormsSensor(ModernFormsDeviceEntity, SensorEntity):
    """Defines a Modern Forms binary sensor."""

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: ModernFormsDataUpdateCoordinator,
        name: str,
        icon: str,
        key: str,
        unit_of_measure: str,
    ) -> None:
        """Initialize Modern Forms switch."""
        self._key = key
        super().__init__(
            entry_id=entry_id, coordinator=coordinator, name=name, icon=icon
        )
        self._attr_unique_id = f"{self.coordinator.data.info.mac_address}_{self._key}"
        self._attr_unit_of_measurement = unit_of_measure


class ModernFormsLightTimerRemainingTimeSensor(ModernFormsSensor):
    """Defines the Modern Forms Light Timer remaining time sensor."""

    def __init__(
        self, entry_id: str, coordinator: ModernFormsDataUpdateCoordinator
    ) -> None:
        """Initialize Modern Forms Away mode switch."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            icon="mdi:timer-outline",
            key="light_timer_remaining_time",
            name=f"{coordinator.data.info.device_name} Light Timer Remaining Time",
            unit_of_measure=TIME_SECONDS,
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.data.state.light_sleep_timer == CLEAR_TIMER:
            return str(CLEAR_TIMER)

        difference = (
            datetime.fromtimestamp(self.coordinator.data.state.light_sleep_timer)
            - datetime.now()
        )
        return str(round(difference.total_seconds()))


class ModernFormsFanTimerRemainingTimeSensor(ModernFormsSensor):
    """Defines the Modern Forms Light Timer remaining time sensor."""

    def __init__(
        self, entry_id: str, coordinator: ModernFormsDataUpdateCoordinator
    ) -> None:
        """Initialize Modern Forms Away mode switch."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            icon="mdi:timer-outline",
            key="fan_timer_remaining_time",
            name=f"{coordinator.data.info.device_name} Fan Timer Remaining Time",
            unit_of_measure=TIME_SECONDS,
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.data.state.fan_sleep_timer == CLEAR_TIMER:
            return str(CLEAR_TIMER)

        difference = (
            datetime.fromtimestamp(self.coordinator.data.state.fan_sleep_timer)
            - datetime.now()
        )
        return str(round(difference.total_seconds()))
