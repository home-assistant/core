"""Support for Palazzetti climates."""

from typing import Any

from pypalazzetti.exceptions import CommunicationError, ValidationError

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, FAN_AUTO, FAN_HIGH, FAN_MODES
from .coordinator import PalazzettiConfigEntry, PalazzettiDataUpdateCoordinator
from .entity import PalazzettiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PalazzettiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Palazzetti climates based on a config entry."""
    async_add_entities([PalazzettiClimateEntity(entry.runtime_data)])


class PalazzettiClimateEntity(PalazzettiEntity, ClimateEntity):
    """Defines a Palazzetti climate."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = DOMAIN
    _attr_target_temperature_step = 1.0
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: PalazzettiDataUpdateCoordinator) -> None:
        """Initialize Palazzetti climate."""
        super().__init__(coordinator)
        client = coordinator.client
        mac = coordinator.config_entry.unique_id
        self._attr_unique_id = mac
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        self._attr_min_temp = client.target_temperature_min
        self._attr_max_temp = client.target_temperature_max
        self._attr_fan_modes = list(
            map(str, range(client.fan_speed_min, client.fan_speed_max + 1))
        )
        if client.has_fan_high:
            self._attr_fan_modes.append(FAN_HIGH)
        if client.has_fan_auto:
            self._attr_fan_modes.append(FAN_AUTO)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat or off mode."""
        return HVACMode.HEAT if self.coordinator.client.is_on else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """Return hvac action ie. heating or idle."""
        return (
            HVACAction.HEATING
            if self.coordinator.client.is_heating
            else HVACAction.IDLE
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        try:
            await self.coordinator.client.set_on(hvac_mode != HVACMode.OFF)
        except CommunicationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except ValidationError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="on_off_not_available"
            ) from err
        await self.coordinator.async_refresh()

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return self.coordinator.client.room_temperature

    @property
    def target_temperature(self) -> int | None:
        """Return the temperature."""
        return self.coordinator.client.target_temperature

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        temperature = int(kwargs[ATTR_TEMPERATURE])
        try:
            await self.coordinator.client.set_target_temperature(temperature)
        except CommunicationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except ValidationError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_target_temperature",
                translation_placeholders={
                    "value": str(temperature),
                },
            ) from err
        await self.coordinator.async_refresh()

    @property
    def fan_mode(self) -> str | None:
        """Return the fan mode."""
        api_state = self.coordinator.client.current_fan_speed()
        return FAN_MODES[api_state]

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        try:
            if fan_mode == FAN_HIGH:
                await self.coordinator.client.set_fan_high()
            elif fan_mode == FAN_AUTO:
                await self.coordinator.client.set_fan_auto()
            else:
                await self.coordinator.client.set_fan_speed(FAN_MODES.index(fan_mode))
        except CommunicationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except ValidationError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_fan_mode",
                translation_placeholders={
                    "value": fan_mode,
                },
            ) from err
        await self.coordinator.async_refresh()
