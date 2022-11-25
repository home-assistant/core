"""Edilkamin integration entity."""
from typing import Any, cast

import edilkamin

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .const import LOGGER

power_to_hvac = {
    edilkamin.Power.OFF: HVACMode.OFF,
    edilkamin.Power.ON: HVACMode.HEAT,
}
hvac_mode_to_power = {hvac: power for (power, hvac) in power_to_hvac.items()}


class EdilkaminEntity(ClimateEntity):
    """Representation of a stove."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(
        self,
        username: str,
        password: str,
        mac_address: str,
    ) -> None:
        """Create the Edilkamin entity.

        Use:
        - the username/password to login
        - the MAC address that identifies the stove
        """
        self._attr_name = f"Stove ({mac_address})"
        self._attr_unique_id = mac_address
        self._username = username
        self._password = password
        self._mac_address = mac_address
        self._device_info = None

    def refresh_token(self) -> str:
        """Login to refresh the token."""
        return cast(str, edilkamin.sign_in(self._username, self._password))

    def update(self) -> None:
        """Get the latest data and update the relevant Entity attributes."""
        token = self.refresh_token()
        self._device_info = edilkamin.device_info(token, self._mac_address)
        power = edilkamin.device_info_get_power(self._device_info)
        self._attr_hvac_mode = power_to_hvac[power]
        self._attr_target_temperature = edilkamin.device_info_get_target_temperature(
            self._device_info
        )
        self._attr_current_temperature = (
            edilkamin.device_info_get_environment_temperature(self._device_info)
        )

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        token = self.refresh_token()
        edilkamin.set_target_temperature(token, self._mac_address, temperature)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        LOGGER.debug("Setting async hvac mode: %s", hvac_mode)
        if hvac_mode not in hvac_mode_to_power:
            LOGGER.warning("Unsupported mode: %s", hvac_mode)
            return
        power = hvac_mode_to_power[hvac_mode]
        token = self.refresh_token()
        edilkamin.set_power(token, self._mac_address, power)
