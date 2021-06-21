"""ClimateEntity for frigidaire integration."""
from __future__ import annotations

import logging

import frigidaire

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up frigidaire from a config entry."""
    client = hass.data[DOMAIN][entry.entry_id]

    def get_entities(username: str, password: str) -> frigidaire.Frigidaire:
        return client.get_appliances()

    appliances = await hass.async_add_executor_job(
        get_entities, entry.data["username"], entry.data["password"]
    )

    async_add_entities(
        [FrigidaireClimate(client, appliance) for appliance in appliances],
        update_before_add=True,
    )


class FrigidaireClimate(ClimateEntity):
    """Representation of a Frigidaire appliance."""

    def __init__(self, client, appliance):
        """Build FrigidaireClimate.

        client: the client used to contact the frigidaire API
        appliance: the basic information about the frigidaire appliance, used to contact the API
        """

        self._client = client
        self._appliance = appliance
        self._details = None

        # Entity Class Attributes
        self._attr_unique_id = appliance.appliance_id
        self._attr_name = appliance.nickname
        self._attr_supported_features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE
        self._attr_target_temperature_step = 1

        # Although we can access the Frigidaire API to get updates, they are
        # not reflected immediately after making a request. To improve the UX
        # around this, we set assume_state to True
        self._attr_assumed_state = True

        self._attr_fan_modes = [
            FAN_AUTO,
            FAN_LOW,
            FAN_MEDIUM,
            FAN_HIGH,
        ]

        self._attr_hvac_modes = [
            HVAC_MODE_OFF,
            HVAC_MODE_COOL,
            HVAC_MODE_AUTO,
            HVAC_MODE_FAN_ONLY,
        ]

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the entity."""
        return self._attr_assumed_state

    @property
    def unique_id(self):
        """Return unique ID based on Frigidaire ID."""
        return self._attr_unique_id

    @property
    def name(self):
        """Return the name of the entity."""
        return self._attr_name

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._attr_supported_features

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._attr_hvac_modes

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._attr_target_temperature_step

    @property
    def fan_modes(self):
        """List of available fan modes."""
        return self._attr_fan_modes

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        convert = {
            frigidaire.Unit.FAHRENHEIT.value: TEMP_FAHRENHEIT,
            frigidaire.Unit.CELSIUS.value: TEMP_CELSIUS,
        }

        unit = self._details.for_code(
            frigidaire.HaclCode.TEMPERATURE_REPRESENTATION
        ).string_value

        return convert[unit]

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return (
            self._details.for_code(frigidaire.HaclCode.TARGET_TEMPERATURE)
            .containers.for_id(frigidaire.ContainerId.TEMPERATURE)
            .number_value
        )

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        convert = {
            frigidaire.Mode.OFF.value: HVAC_MODE_OFF,
            frigidaire.Mode.COOL.value: HVAC_MODE_COOL,
            frigidaire.Mode.FAN.value: HVAC_MODE_FAN_ONLY,
            frigidaire.Mode.ECO.value: HVAC_MODE_AUTO,
        }

        frigidaire_mode = self._details.for_code(
            frigidaire.HaclCode.AC_MODE
        ).number_value

        return convert[frigidaire_mode]

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return (
            self._details.for_code(frigidaire.HaclCode.AMBIENT_TEMPERATURE)
            .containers.for_id(frigidaire.ContainerId.TEMPERATURE)
            .number_value
        )

    @property
    def fan_mode(self):
        """Return the fan setting."""
        convert = {
            frigidaire.FanSpeed.OFF.value: FAN_OFF,  # when the AC is off
            frigidaire.FanSpeed.AUTO.value: FAN_AUTO,
            frigidaire.FanSpeed.LOW.value: FAN_LOW,
            frigidaire.FanSpeed.MEDIUM.value: FAN_MEDIUM,
            frigidaire.FanSpeed.HIGH.value: FAN_HIGH,
        }
        fan_speed = self._details.for_code(frigidaire.HaclCode.AC_FAN_SPEED_SETTING)

        if not fan_speed:
            return FAN_OFF

        return convert[fan_speed.number_value]

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self.temperature_unit == TEMP_FAHRENHEIT:
            return 60
        else:
            return 16

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self.temperature_unit == TEMP_FAHRENHEIT:
            return 90
        else:
            return 32

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        temperature = int(temperature)

        self._client.execute_action(
            self._appliance, frigidaire.Action.set_temperature(temperature)
        )

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        convert = {
            FAN_AUTO: frigidaire.FanSpeed.AUTO,
            FAN_LOW: frigidaire.FanSpeed.LOW,
            FAN_MEDIUM: frigidaire.FanSpeed.MEDIUM,
            FAN_HIGH: frigidaire.FanSpeed.HIGH,
        }

        # Guard against unexpected fan modes
        if fan_mode not in convert:
            return

        action = frigidaire.Action.set_fan_speed(convert[fan_mode])
        self._client.execute_action(self._appliance, action)

    def set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self._client.execute_action(
                self._appliance, frigidaire.Action.set_power(frigidaire.Power.OFF)
            )
            return

        convert = {
            HVAC_MODE_AUTO: frigidaire.Mode.ECO,
            HVAC_MODE_FAN_ONLY: frigidaire.Mode.FAN,
            HVAC_MODE_COOL: frigidaire.Mode.COOL,
        }

        # Guard against unexpected hvac modes
        if hvac_mode not in convert:
            return

        # Turn on if not currently on.
        if self._details.for_code(frigidaire.HaclCode.AC_MODE) == 0:
            self._client.execute_action(
                self._appliance, frigidaire.Action.set_power(frigidaire.Power.ON)
            )

        self._client.execute_action(
            self._appliance, frigidaire.Action.set_mode(convert[hvac_mode])
        )

    def update(self):
        """Retrieve latest state and updates the details."""
        try:
            details = self._client.get_appliance_details(self._appliance)
            self._details = details
            self._attr_available = True
        except (frigidaire.FrigidaireException):
            if self.available:
                _LOGGER.error("Failed to connect to Frigidaire servers")
            self._attr_available = False
