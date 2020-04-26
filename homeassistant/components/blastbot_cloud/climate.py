"""Platform for AC integration."""
from typing import List

from blastbot_cloud_api.models.control import Control

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVAC_MODE_COOL,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Blastbot Cloud platform."""

    # Get API object from data
    api = hass.data[DOMAIN][entry.entry_id]

    # Add switches
    acs = await api.async_get_acs()
    async_add_entities(BlastbotACEntity(ac) for ac in acs)


class BlastbotACEntity(ClimateEntity):
    """Representation of a Blastbot AC."""

    def __init__(self, control: Control) -> None:
        """Initialize the AC."""
        self._control = control

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{DOMAIN}_c{self._control.id}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._control.device["connected"]

    @property
    def name(self) -> str:
        """Return the name of the ac."""
        return self._control.name

    @property
    def temperature_unit(self) -> str:
        """Specify temperature unit."""
        return TEMP_CELSIUS

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 18

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 30

    @property
    def current_temperature(self) -> float:
        """Return last known temperature."""
        temp = self._control.temperature
        if temp is None:
            temp = 0
        else:
            temp = float(temp)
        return temp

    @property
    def target_temperature(self) -> float:
        """Return configured target temperature."""
        return float(self._control.acSettings["temperature"])

    @property
    def target_temperature_step(self) -> float:
        """Specify target temperature steps."""
        return 1

    @property
    def hvac_mode(self) -> str:
        """Return current HVAC mode."""
        return (
            HVAC_MODE_COOL
            if self._control.acSettings["state"] == "on"
            else HVAC_MODE_OFF
        )

    @property
    def hvac_modes(self) -> List[str]:
        """Return supported HVAC modes."""
        return [HVAC_MODE_OFF, HVAC_MODE_COOL]

    @property
    def fan_mode(self) -> str:
        """Return current fan mode."""
        mode = self._control.acSettings["fan"]
        if mode == "auto":
            return FAN_AUTO
        if mode == "low":
            return FAN_LOW
        if mode == "medium":
            return FAN_MEDIUM
        if mode == "high":
            return FAN_HIGH
        return FAN_AUTO

    @property
    def fan_modes(self) -> List[str]:
        """Return supported fan modes."""
        return [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    @property
    def supported_features(self) -> int:
        """Return supported temperatures."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE

    async def async_update(self) -> None:
        """Synchronize state with ac."""
        await self._control.async_update()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        state = "on" if hvac_mode == HVAC_MODE_COOL else "off"
        await self._control.async_control_ac(state=state)

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        fan = "auto"
        if fan_mode == FAN_AUTO:
            fan = "auto"
        if fan_mode == FAN_LOW:
            fan = "low"
        if fan_mode == FAN_MEDIUM:
            fan = "medium"
        if fan_mode == FAN_HIGH:
            fan = "high"
        await self._control.async_control_ac(fan=fan)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        temperature = str(int(temp))
        await self._control.async_control_ac(temperature=temperature)

    @property
    def device_info(self):
        """Return device info."""
        model = "Blastbot Device"
        d_id = self._control.device["id"]
        d_type = self._control.device["type"]
        d_name = self._control.device["name"]
        if d_type == "blastbot-ir":
            model = "Blastbot Smart Control"
        if d_type == "blastbot-hub":
            model = "Blastbot Hub"

        bridge_id = self._control.device["bridgeId"]

        info = {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, f"d{d_id}")
            },
            "name": d_name,
            "manufacturer": "Blastbot",
            "model": model,
            "sw_version": self._control.device["version"],
        }

        if bridge_id is not None:
            info["via_device"] = (DOMAIN, f"d{bridge_id}")

        return info
