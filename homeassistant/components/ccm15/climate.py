"""Climate device for CCM15 coordinator."""
import logging

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .coordinator import CCM15Coordinator

_LOGGER = logging.getLogger(__name__)


class CCM15Climate(ClimateEntity):
    """Climate device for CCM15 coordinator."""

    def __init__(
        self, ac_name: str, host: str, port: int, coordinator: CCM15Coordinator
    ) -> None:
        """Create a climate device managed from a coordinator."""
        self._ac_name = ac_name
        self._host = host
        self._port = port
        self._coordinator = coordinator
        self._data: dict[str, int] = {}
        self._is_on = False
        self._current_temp = None
        self._target_temp = None
        self._operation_mode = None
        self._fan_mode = None
        self._swing_mode = None
        self._available = False
        self.update()

    @property
    def unique_id(self):
        """Return unique id."""
        return f"{self._host}:{self._port}:{self._ac_name}"

    @property
    def name(self):
        """Return name."""
        return f"{self._ac_name} thermostat"

    @property
    def should_poll(self) -> bool:
        """Return if should poll."""
        return True

    @property
    def temperature_unit(self):
        """Return temperature unit."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self):
        """Return current temperature."""
        return self._current_temp

    @property
    def target_temperature(self):
        """Return target temperature."""
        return self._target_temp

    @property
    def target_temperature_step(self):
        """Return target temperature step."""
        return 1

    @property
    def hvac_mode(self):
        """Return hvac mode."""
        return self._operation_mode

    @property
    def hvac_modes(self):
        """Return hvac modes."""
        return [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]

    @property
    def fan_mode(self):
        """Return fan mode."""
        return self._fan_mode

    @property
    def fan_modes(self):
        """Return fan modes."""
        return [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    @property
    def swing_mode(self):
        """Return swing mode."""
        return self._swing_mode

    @property
    def swing_modes(self) -> list[str]:
        """Return swing modes."""
        return [SWING_OFF, SWING_VERTICAL, SWING_HORIZONTAL, SWING_BOTH]

    @property
    def supported_features(self):
        """Return supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
        )

    def set_temperature(self, **kwargs):
        """Set the target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temp = temperature
        self._coordinator.set_temperature(self._ac_name, temperature)
        self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode):
        """Set the hvac mode."""
        self._operation_mode = hvac_mode
        self._coordinator.set_operation_mode(self._ac_name, hvac_mode)
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan_mode):
        """Set the fan mode."""
        self._fan_mode = fan_mode
        self._coordinator.set_fan_mode(self._ac_name, fan_mode)
        self.schedule_update_ha_state()

    def set_swing_mode(self, swing_mode):
        """Set the swing mode."""
        self._swing_mode = swing_mode
        self._coordinator.set_swing_mode(self._ac_name, swing_mode)
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn off."""
        self._is_on = False
        self._coordinator.turn_off(self._ac_name)
        self.schedule_update_ha_state()

    def turn_on(self):
        """Turn on."""
        self._is_on = True
        self._coordinator.turn_on(self._ac_name)
        self.schedule_update_ha_state()

    def update(self):
        """Update the data from the thermostat."""
        self._coordinator.get_acdata(self._ac_name)
        self.schedule_update_ha_state()
