"""Climate module for the Heatmiser NetMonitor integration."""
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .heatmiser_hub import HeatmiserHub, HeatmiserStat


def setup_platform(hass: HomeAssistant, config: ConfigType) -> None:
    """Set up the Heatmiser platform."""
    # Assign configuration variables.
    # The configuration check takes care they are present.
    host = config["host"]
    username = config["username"]
    password = config.get("password")

    hub = HeatmiserHub(host, username, password, hass)
    hub.get_devices_async()


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up Heatmiser climate based on config_entry."""
    host = entry.data.get("host")
    username = entry.data.get("username")
    password = entry.data.get("password")
    hub = HeatmiserHub(host, username, password, hass)
    devices = await hub.get_devices_async()
    async_add_entities(HeatmiserClimate(stat, hub) for stat in devices)


class HeatmiserClimate(ClimateEntity):
    """Climate object for a Heatmiser stat."""

    def __init__(self, stat: HeatmiserStat, hub: HeatmiserHub) -> None:
        """Set up Heatmiser climate entity based on a stat."""
        self._supported_features = SUPPORT_TARGET_TEMPERATURE
        self._attr_hvac_modes = {HVAC_MODE_HEAT, HVAC_MODE_OFF}
        self.stat = stat
        self.hub = hub

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self.stat.name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self.stat.id

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.stat.current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.stat.target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        await self.hub.set_temperature_async(self.stat.name, kwargs["temperature"])
        await self.async_update()

    @property
    def hvac_action(self):
        """Return the current state."""
        return self.stat.current_state

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self.stat.hvac_mode

    async def async_set_hvac_mode(self, hvac_mode) -> None:
        """Set HVAC mode."""
        await self.hub.set_mode_async(self.stat.name, hvac_mode)
        await self.async_update()

    async def async_update(self) -> None:
        """Retrieve latest state."""
        new_stat_state = await self.hub.get_device_status_async(self.stat.name)
        new_stat_state.id = self.stat.id
        self.stat = new_stat_state

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return DeviceInfo(manufacturer="Heatmiser", name=self.stat.name)
