"""Support for Palazzetti climates."""

from typing import Any, cast

from palazzetti_sdk_local_api.exceptions import InvalidStateTransitionError

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ACTION_NOT_UNAVAILABLE,
    API_HW_VERSION,
    API_NAME,
    API_SW_VERSION,
    DOMAIN,
    FAN_AUTO,
    FAN_HIGH,
    FAN_MODE,
    FAN_MODES,
    FAN_SILENT,
    HEATING_STATUSES,
    MAC,
    MODE,
    PALAZZETTI,
    ROOM_TEMPERATURE,
    TARGET_TEMPERATURE,
)
from .coordinator import PalazzettiDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Palazzetti climates based on a config entry."""
    coordinator: PalazzettiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[PalazzettiClimateEntity] = []
    await coordinator.async_config_entry_first_refresh()
    entities.append(PalazzettiClimateEntity(coordinator=coordinator))
    async_add_entities(entities)


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

    def __init__(
        self,
        *,
        coordinator: PalazzettiDataUpdateCoordinator,
    ) -> None:
        """Initialize Palazzetti climate."""
        super().__init__(coordinator=coordinator)
        self.hub = coordinator.hub

        # TURN_OFF and TURN_ON are not always available. An update coordinator listener will add them when possible.
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        )
        coordinator.async_add_listener(self._update_modes_and_features)

        name = self.hub.product.response_json[API_NAME]
        self._attr_unique_id = coordinator.entry.data[MAC]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.data[MAC])},
            name=PALAZZETTI,
            manufacturer=PALAZZETTI,
            sw_version=self.hub.product.response_json[API_SW_VERSION],
            hw_version=self.hub.product.response_json[API_HW_VERSION],
        )
        self._attr_name = name

    @callback
    def _update_modes_and_features(self) -> None:
        if self.hub.product.get_data_config_object().flag_has_switch_on_off:
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )
            self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        else:
            self._attr_supported_features &= ~(
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )
            self._attr_hvac_modes = [self.hvac_mode]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat or off mode."""
        api_state = self.coordinator.data[MODE]
        return HVACMode.HEAT if api_state in HEATING_STATUSES else HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        try:
            if hvac_mode == HVACMode.OFF:
                self.hass.async_add_executor_job(self.hub.product.power_off)
            else:
                self.hass.async_add_executor_job(self.hub.product.power_on)
        except InvalidStateTransitionError as err:
            raise HomeAssistantError(
                err, translation_domain=DOMAIN, translation_key=ACTION_NOT_UNAVAILABLE
            ) from err

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        api_state = self.coordinator.data[ROOM_TEMPERATURE]
        return api_state if isinstance(api_state, float) else None

    @property
    def target_temperature(self) -> int | None:
        """Return the temperature."""
        api_state = self.coordinator.data[TARGET_TEMPERATURE]
        return api_state if isinstance(api_state, int) else None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        temperature = cast(float, kwargs.get(ATTR_TEMPERATURE))
        await self.hub.product.async_set_setpoint(int(temperature))

    @property
    def fan_mode(self) -> str | None:
        """Return the fan mode."""
        api_state = self.coordinator.data[FAN_MODE]
        return FAN_MODES[api_state]

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if fan_mode == FAN_SILENT:
            await self.hub.product.async_set_fan_silent_mode()
        elif fan_mode == FAN_HIGH:
            await self.hub.product.async_set_fan_high_mode()
        elif fan_mode == FAN_AUTO:
            await self.hub.product.async_set_fan_auto_mode()
        else:
            await self.hub.product.async_set_fan(fan=1, value=FAN_MODES.index(fan_mode))
