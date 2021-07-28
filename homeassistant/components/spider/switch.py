"""Support for Spider switches."""
from __future__ import annotations

from typing import Any

from spiderpy.devices.powerplug import SpiderPowerPlug
from spiderpy.spiderapi import SpiderApi

from homeassistant.components.switch import SwitchEntity

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize a Spider Power Plug."""
    api = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PowerPlug(api, entity)
            for entity in await hass.async_add_executor_job(api.get_power_plugs)
        ]
    )


class PowerPlug(SwitchEntity):
    """Representation of a Spider Power Plug."""

    def __init__(self, api: SpiderApi, power_plug: SpiderPowerPlug) -> None:
        """Initialize the Spider Power Plug."""
        self.api: SpiderApi = api
        self.power_plug: SpiderPowerPlug = power_plug

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.power_plug.id)},
            manufacturer=self.power_plug.manufacturer,
            model=self.power_plug.model,
            name=self.power_plug.name,
        )

    @property
    def unique_id(self) -> str | Any:
        """Return the ID of this switch."""
        return self.power_plug.id

    @property
    def name(self) -> str | Any:
        """Return the name of the switch if any."""
        return self.power_plug.name

    @property
    def is_on(self) -> bool | Any:
        """Return true if switch is on. Standby is on."""
        return self.power_plug.is_on

    @property
    def available(self) -> bool | Any:
        """Return true if switch is available."""
        return self.power_plug.is_available

    def turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        self.power_plug.turn_on()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        self.power_plug.turn_off()

    def update(self) -> None:
        """Get the latest data."""
        self.power_plug = self.api.get_power_plug(self.power_plug.id)
