"""Climate platform for GKP integration."""

from collections.abc import Coroutine
import logging
from typing import Any, override

from gkphomepython import (
    SETPOINT_MAX,
    SETPOINT_MIN,
    GkpError,
    GkpMode,
    GkpRateLimitError,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GkpConfigEntry
from .const import (
    DOMAIN,
    GKP_MODE_TO_HVAC,
    GKP_MODE_TO_PRESET,
    HVAC_TO_GKP_MODE,
    PRESET_MODES,
    PRESET_TO_GKP_MODE,
)
from .entity import GkpEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GkpConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GKP climate entities from a config entry."""
    device_coordinators = entry.runtime_data.device_coordinators
    known_device_ids: set[str] = set()

    @callback
    def _check_new_thermostats() -> None:
        """Add entities for new thermostats."""
        new_device_ids = set(device_coordinators) - known_device_ids
        if not new_device_ids:
            return

        _LOGGER.debug(
            "Adding climate entities for %d new thermostat(s)", len(new_device_ids)
        )
        known_device_ids.update(new_device_ids)
        async_add_entities(
            GkpClimate(device_coordinators[device_id]) for device_id in new_device_ids
        )

    _check_new_thermostats()

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{entry.entry_id}_new_device",
            _check_new_thermostats,
        )
    )


class GkpClimate(GkpEntity, ClimateEntity):
    """Representation of a GKP radiator as a climate entity."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF, HVACMode.AUTO]
    _attr_preset_modes = PRESET_MODES
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = PRECISION_HALVES
    _attr_min_temp = SETPOINT_MIN
    _attr_max_temp = SETPOINT_MAX
    _attr_name = None
    _attr_translation_key = "thermostat"

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.thermostat.current_temperature

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the temperature setpoint."""
        return self.thermostat.setpoint

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac mode."""
        mode = self.thermostat.mode
        return None if mode is None else GKP_MODE_TO_HVAC[mode]

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        mode = self.thermostat.mode
        if mode is None:
            return None
        if mode is GkpMode.OFF:
            return HVACAction.OFF
        return HVACAction.HEATING if self.thermostat.is_heating else HVACAction.IDLE

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        mode = self.thermostat.mode
        return None if mode is None else GKP_MODE_TO_PRESET.get(mode)

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self._async_set_mode(HVAC_TO_GKP_MODE[hvac_mode], "set_hvac_mode_error")

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self._async_set_mode(
            PRESET_TO_GKP_MODE[preset_mode], "set_preset_mode_error"
        )

    async def _async_set_mode(self, mode: GkpMode, error_key: str) -> None:
        """Send a new mode to the device."""
        await self._async_send_command(
            self.coordinator.client.set_mode(self.device_id, mode), error_key
        )
        _LOGGER.debug("Successfully set mode %s for %s", mode.name, self.device_id)
        await self._async_refresh_after_command()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature.

        In AUTO mode the program drives the setpoint, so the device is put in
        boost at the requested temperature, like the GKP application.
        """
        temperature: float = kwargs[ATTR_TEMPERATURE]
        hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None:
            self._valid_mode_or_raise("hvac", hvac_mode, self.hvac_modes)
        mode = (
            self.thermostat.mode if hvac_mode is None else HVAC_TO_GKP_MODE[hvac_mode]
        )
        if (
            mode is None
            or not mode.setpoint_adjustable
            or (hvac_mode is not None and mode is GkpMode.AUTO)
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="setpoint_not_adjustable",
                translation_placeholders={"entity_id": self.entity_id},
            )

        await self._async_send_command(
            self.coordinator.client.set_temperature(self.device_id, mode, temperature),
            "set_temperature_error",
        )
        _LOGGER.debug(
            "Successfully set temperature to %s in %s mode for %s",
            temperature,
            mode.name,
            self.device_id,
        )
        await self._async_refresh_after_command()

    async def _async_send_command(
        self, command: Coroutine[Any, Any, None], error_key: str
    ) -> None:
        """Send a command, translating API errors."""
        try:
            await command
        except GkpRateLimitError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rate_limited",
                translation_placeholders={"retry_after": str(err.retry_after)},
            ) from err
        except GkpError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=error_key,
            ) from err

    async def _async_refresh_after_command(self) -> None:
        """Poll the device quickly until the command is reflected."""
        self.coordinator.trigger_fast_polling()
        await self.coordinator.async_refresh()
