"""Support for Schluter thermostats."""
from __future__ import annotations

import logging
from typing import Any

from requests import RequestException
import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    SCAN_INTERVAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_SCAN_INTERVAL, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

#from . import DATA_SCHLUTER_API, DATA_SCHLUTER_SESSION, DOMAIN, schluter_auth
#from . import DATA_SCHLUTER_API, DATA_SCHLUTER_USER, DATA_SCHLUTER_PASS, DATA_SCHLUTER_SESSIONFILE, DOMAIN, schluter_auth
from . import DOMAIN, schluter_auth_update, DATA_SCHLUTER_API

_LOGGER = logging.getLogger(__name__)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=1))}
)

def sch_get_thermostats(hass_domain):
    sid = schluter_auth_update(hass_domain);
    api = hass_domain[DATA_SCHLUTER_API];

    if sid is not None:
         return api.get_thermostats(sid);
    else:
         return None;

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Schluter thermostats."""
    if discovery_info is None:
        return
    #session_id = hass.data[DOMAIN][DATA_SCHLUTER_SESSION]
    hass_domain = hass.data[DOMAIN];

    async def async_update_data():
        try:
            thermostats = await hass.async_add_executor_job(
                sch_get_thermostats, hass_domain
            )
        except RequestException as err:
            raise UpdateFailed(f"Error communicating with Schluter API: {err}") from err

        if thermostats is None:
            return {}

        return {thermo.serial_number: thermo for thermo in thermostats}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="schluter",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_refresh()

    async_add_entities(
        SchluterThermostat(coordinator, serial_number)
        for serial_number, thermostat in coordinator.data.items()
    )


class SchluterThermostat(CoordinatorEntity, ClimateEntity):
    """Representation of a Schluter thermostat."""

    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, serial_number):
        """Initialize the thermostat."""
        super().__init__(coordinator)
        
        #
        # This dict will be updated inside schluter_auth_update().
        #
        self._hass_domain = coordinator.hass.data[DOMAIN];
        self._serial_number = serial_number;
        #self._session_id = session_id

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._serial_number

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self.coordinator.data[self._serial_number].name

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.coordinator.data[self._serial_number].temperature

    @property
    def hvac_action(self) -> HVACAction:
        """Return current operation. Can only be heating or idle."""
        if self.coordinator.data[self._serial_number].is_heating:
            return HVACAction.HEATING
        return HVACAction.IDLE

    # tcp: there is also .manual_temp which it seems is the last manually setup temp
    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.coordinator.data[self._serial_number].set_point_temp

    @property
    def min_temp(self):
        """Identify min_temp in Schluter API."""
        return self.coordinator.data[self._serial_number].min_temp

    @property
    def max_temp(self):
        """Identify max_temp in Schluter API."""
        return self.coordinator.data[self._serial_number].max_temp

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Mode is always heating, so do nothing."""

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temp = None
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        serial_number = self.coordinator.data[self._serial_number].serial_number
        _LOGGER.debug("Setting thermostat temperature: %s", target_temp)

        try:
            if target_temp is not None:
                sid = schluter_auth_update(self._hass_domain);
                if sid is not None:
                    api = self._hass_domain[DATA_SCHLUTER_API];
                    api.set_temperature(sid, serial_number, target_temp)
        except RequestException as ex:
            _LOGGER.error("An error occurred while setting temperature: %s", ex)
