"""Provides number enties for Home Connect."""

import logging

from homeconnect.api import HomeConnectError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_CONSTRAINTS, ATTR_MAX, ATTR_MIN, ATTR_VALUE, DOMAIN
from .entity import HomeConnectEntityDescription, HomeConnectInteractiveEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""

    def get_entities():
        """Get a list of entities."""
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        return [
            HomeConnectNumberSetting(device, setting)
            for setting in BSH_NUMBER_SETTINGS
            for device in hc_api.devices
            if setting.key in device.appliance.status
        ]

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectBinarySensorEntityDescription(
    HomeConnectEntityDescription,
    NumberEntityDescription,
    frozen_or_thawed=True,
):
    """Description of a Home Connect binary sensor entity."""


class HomeConnectNumberSetting(HomeConnectInteractiveEntity, NumberEntity):
    """Number setting class for Home Connect."""

    entity_description: HomeConnectBinarySensorEntityDescription

    async def async_set_native_value(self, value: float) -> None:
        """Set the native value of the entity."""
        await self.async_set_value_to_appliance(value)

    async def async_update(self) -> None:
        """Update the number setting status."""
        if not (data := self.status):
            return
        self._attr_native_value = data.get(ATTR_VALUE, None)
        _LOGGER.debug("Updated, new value: %s", self._attr_native_value)

        if (
            hasattr(self, "_attr_native_min_value")
            and self._attr_native_min_value is not None
            and hasattr(self, "_attr_native_max_value")
            and self._attr_native_max_value is not None
            and hasattr(self, "_attr_native_step")
            and self._attr_native_step is not None
        ):
            return
        try:
            data = self.device.appliance.get(f"/status/{self.bsh_key}")
        except HomeConnectError as err:
            _LOGGER.error("An error occurred: %s", err)
            return
        if not data or not (constraints := data.get(ATTR_CONSTRAINTS)):
            return
        self._attr_native_max_value = constraints.get(ATTR_MAX, None)
        self._attr_native_min_value = constraints.get(ATTR_MIN, None)
        self._attr_native_step = 1 if data.get("Int", None) == "integer" else 0.1


BSH_NUMBER_SETTINGS = (
    HomeConnectBinarySensorEntityDescription(
        key="Refrigeration.FridgeFreezer.Setting.SetpointTemperatureRefrigerator",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectBinarySensorEntityDescription(
        key="Refrigeration.FridgeFreezer.Setting.SetpointTemperatureFreezer",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectBinarySensorEntityDescription(
        key="Refrigeration.Common.Setting.BottleCooler.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectBinarySensorEntityDescription(
        key="Refrigeration.Common.Setting.ChillerLeft.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectBinarySensorEntityDescription(
        key="Refrigeration.Common.Setting.ChillerCommon.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectBinarySensorEntityDescription(
        key="Refrigeration.Common.Setting.ChillerRight.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectBinarySensorEntityDescription(
        key="Refrigeration.Common.Setting.WineCompartment.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectBinarySensorEntityDescription(
        key="Refrigeration.Common.Setting.WineCompartment2.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    HomeConnectBinarySensorEntityDescription(
        key="Refrigeration.Common.Setting.WineCompartment3.SetpointTemperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
)
