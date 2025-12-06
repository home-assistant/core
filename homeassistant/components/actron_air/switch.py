"""Switch platform for Actron Air integration."""

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ActronAirConfigEntry, ActronAirSystemCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActronAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Actron Air switch entities."""
    system_coordinators = entry.runtime_data.system_coordinators
    entities: list[SwitchEntity] = []

    for coordinator in system_coordinators.values():
        entities.append(AwayModeSwitch(coordinator))
        entities.append(ContinuousFanSwitch(coordinator))
        entities.append(QuietModeSwitch(coordinator))

        if coordinator.data.user_aircon_settings.turbo_supported:
            entities.append(TurboModeSwitch(coordinator))

    async_add_entities(entities)


class BaseSwitchEntity(CoordinatorEntity[ActronAirSystemCoordinator], SwitchEntity):
    """Base class for Actron Air switches."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._serial_number = coordinator.serial_number
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
        )


class AwayModeSwitch(BaseSwitchEntity):
    """Actron Air away mode switch."""

    _attr_translation_key = "away_mode"

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the away mode switch."""
        super().__init__(coordinator)
        self._attr_unique_id: str = (
            f"{self._serial_number}-{self._attr_translation_key}"
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.data.user_aircon_settings.away_mode

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the away mode on."""
        await self.coordinator.data.user_aircon_settings.set_away_mode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the away mode off."""
        await self.coordinator.data.user_aircon_settings.set_away_mode(False)


class ContinuousFanSwitch(BaseSwitchEntity):
    """Actron Air continuous fan switch."""

    _attr_translation_key = "continuous_fan"

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the continuous fan switch."""
        super().__init__(coordinator)
        self._attr_unique_id: str = (
            f"{self._serial_number}-{self._attr_translation_key}"
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.data.user_aircon_settings.continuous_fan_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the continuous fan on."""
        await self.coordinator.data.user_aircon_settings.set_continuous_mode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the continuous fan off."""
        await self.coordinator.data.user_aircon_settings.set_continuous_mode(False)


class QuietModeSwitch(BaseSwitchEntity):
    """Actron Air quiet mode switch."""

    _attr_translation_key = "quiet_mode"

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the quiet mode switch."""
        super().__init__(coordinator)
        self._attr_unique_id: str = (
            f"{self._serial_number}-{self._attr_translation_key}"
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.data.user_aircon_settings.quiet_mode_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the quiet mode setting on."""
        await self.coordinator.data.user_aircon_settings.set_quiet_mode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the quiet mode setting off."""
        await self.coordinator.data.user_aircon_settings.set_quiet_mode(False)


class TurboModeSwitch(BaseSwitchEntity):
    """Representation of the Actron Air turbo mode switch."""

    _attr_translation_key = "turbo_mode"

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the turbo mode switch."""
        super().__init__(coordinator)
        self._attr_unique_id: str = (
            f"{self._serial_number}-{self._attr_translation_key}"
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.data.user_aircon_settings.turbo_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the turbo mode on."""
        await self.coordinator.data.user_aircon_settings.set_turbo_mode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the turbo mode off."""
        await self.coordinator.data.user_aircon_settings.set_turbo_mode(False)
