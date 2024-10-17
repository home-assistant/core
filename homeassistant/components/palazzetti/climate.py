"""Support for Palazzetti climates."""

from typing import Any, cast

from pypalazzetti.exceptions import CommunicationError, ValidationError

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_MAC, CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PalazzettiConfigEntry
from .const import (
    ACTION_NOT_UNAVAILABLE,
    DOMAIN,
    FAN_AUTO,
    FAN_HIGH,
    FAN_MODES,
    FAN_SILENT,
    PALAZZETTI,
)
from .coordinator import PalazzettiDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PalazzettiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Palazzetti climates based on a config entry."""
    coordinator: PalazzettiDataUpdateCoordinator = entry.runtime_data
    entities: list[PalazzettiClimateEntity] = []
    if coordinator.client.connected:
        entities.append(
            PalazzettiClimateEntity(
                coordinator=coordinator,
            )
        )
        async_add_entities(entities)
    else:
        raise ConfigEntryNotReady


class PalazzettiClimateEntity(
    CoordinatorEntity[PalazzettiDataUpdateCoordinator], ClimateEntity
):
    """Defines a Palazzetti climate."""

    _attr_has_entity_name = True
    _attr_hvac_modes = []  # The available modes will be set when we know the current state
    _attr_fan_modes = FAN_MODES
    _attr_target_temperature_step = 1.0
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN

    def __init__(self, *, coordinator: PalazzettiDataUpdateCoordinator) -> None:
        """Initialize Palazzetti climate."""
        super().__init__(coordinator=coordinator)
        client = coordinator.client
        self._attr_unique_id = coordinator.config_entry.data[CONF_MAC]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.data[CONF_MAC])},
            name=coordinator.config_entry.data[CONF_NAME],
            manufacturer=PALAZZETTI,
            sw_version=client.sw_version,
            hw_version=client.hw_version,
        )
        self._attr_name = coordinator.config_entry.data[CONF_NAME]
        self._attr_fan_modes = list(
            str(range(client.fan_speed_min, client.fan_speed_max + 1))
        )
        if self.coordinator.client.has_fan_silent:
            self._attr_fan_modes.insert(0, FAN_SILENT)
        if self.coordinator.client.has_fan_high:
            self._attr_fan_modes.append(FAN_HIGH)
        if self.coordinator.client.has_fan_auto:
            self._attr_fan_modes.append(FAN_AUTO)

    @property
    def available(self) -> bool:
        """Is the entity available."""
        return self.coordinator.client.connected

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Supported features."""
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        )
        if self.coordinator.client.has_on_off_switch:
            features |= ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        return features

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """List the hvac modes."""
        if self.coordinator.client.has_on_off_switch:
            return [HVACMode.OFF, HVACMode.HEAT]
        return [self.hvac_mode]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat or off mode."""
        is_heating = bool(self.coordinator.client.is_heating)
        return HVACMode.HEAT if is_heating else HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        try:
            await self.coordinator.client.set_on(hvac_mode != HVACMode.OFF)
        except (CommunicationError, ValidationError) as err:
            raise ServiceValidationError(
                err, translation_domain=DOMAIN, translation_key=ACTION_NOT_UNAVAILABLE
            ) from err

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        api_state = self.coordinator.client.room_temperature
        return api_state if isinstance(api_state, float) else None

    @property
    def target_temperature(self) -> int | None:
        """Return the temperature."""
        api_state = self.coordinator.client.target_temperature
        return api_state if isinstance(api_state, int) else None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        temperature = cast(float, kwargs.get(ATTR_TEMPERATURE))
        await self.coordinator.client.set_target_temperature(int(temperature))

    @property
    def fan_mode(self) -> str | None:
        """Return the fan mode."""
        api_state = self.coordinator.client.fan_speed
        return FAN_MODES[api_state]

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if fan_mode == FAN_SILENT:
            await self.coordinator.client.set_fan_silent()
        elif fan_mode == FAN_HIGH:
            await self.coordinator.client.set_fan_high()
        elif fan_mode == FAN_AUTO:
            await self.coordinator.client.set_fan_auto()
        else:
            await self.coordinator.client.set_fan_speed(FAN_MODES.index(fan_mode))
