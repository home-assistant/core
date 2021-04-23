"""Support for AVM Fritz!Box smarthome switch devices."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    ENERGY_KILO_WATT_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant

from . import FritzBoxEntity
from .const import (
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_LOCKED,
    ATTR_TEMPERATURE_UNIT,
    ATTR_TOTAL_CONSUMPTION,
    ATTR_TOTAL_CONSUMPTION_UNIT,
    CONF_COORDINATOR,
    DOMAIN as FRITZBOX_DOMAIN,
)

ATTR_TOTAL_CONSUMPTION_UNIT_VALUE = ENERGY_KILO_WATT_HOUR


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Fritzbox smarthome switch from ConfigEntry."""
    entities = []
    coordinator = hass.data[FRITZBOX_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    for ain, device in coordinator.data.items():
        if not device.has_switch:
            continue

        entities.append(
            FritzboxSwitch(
                {
                    ATTR_NAME: f"{device.name}",
                    ATTR_ENTITY_ID: f"{device.ain}",
                    ATTR_UNIT_OF_MEASUREMENT: None,
                    ATTR_DEVICE_CLASS: None,
                },
                coordinator,
                ain,
            )
        )

    async_add_entities(entities)


class FritzboxSwitch(FritzBoxEntity, SwitchEntity):
    """The switch class for Fritzbox switches."""

    @property
    def available(self):
        """Return if switch is available."""
        return self.device.present

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self.device.switch_state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.hass.async_add_executor_job(self.device.set_switch_state_on)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.hass.async_add_executor_job(self.device.set_switch_state_off)
        await self.coordinator.async_refresh()

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        attrs = {}
        attrs[ATTR_STATE_DEVICE_LOCKED] = self.device.device_lock
        attrs[ATTR_STATE_LOCKED] = self.device.lock

        if self.device.has_powermeter:
            attrs[
                ATTR_TOTAL_CONSUMPTION
            ] = f"{((self.device.energy or 0.0) / 1000):.3f}"
            attrs[ATTR_TOTAL_CONSUMPTION_UNIT] = ATTR_TOTAL_CONSUMPTION_UNIT_VALUE
        if self.device.has_temperature_sensor:
            attrs[ATTR_TEMPERATURE] = str(
                self.hass.config.units.temperature(
                    self.device.temperature, TEMP_CELSIUS
                )
            )
            attrs[ATTR_TEMPERATURE_UNIT] = self.hass.config.units.temperature_unit
        return attrs

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self.device.power / 1000
