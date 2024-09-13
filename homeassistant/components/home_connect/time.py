"""Provides time enties for Home Connect."""

from datetime import time
import logging

from homeconnect.api import HomeConnectError

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_VALUE, DOMAIN
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
            HomeConnectTimeEntity(device, setting)
            for setting in BSH_TIME_SETTINGS
            for device in hc_api.devices
            if setting.key in device.appliance.status
        ]

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectTimeEntityDescription(
    HomeConnectEntityDescription, TimeEntityDescription
):
    """Description of a Home Connect time entity."""


class HomeConnectTimeEntity(HomeConnectInteractiveEntity, TimeEntity):
    """Time setting class for Home Connect."""

    entity_description: HomeConnectTimeEntityDescription

    async def async_set_value(self, value: time) -> None:
        """Set the native value of the entity."""
        try:
            await self.async_set_value_to_appliance(
                (value.hour * 60 + value.minute) * 60 + value.second
            )
        except HomeConnectError as err:
            _LOGGER.error("Error setting value: %s", err)

    async def async_update(self) -> None:
        """Update the Time setting status."""
        seconds = self.status.get(ATTR_VALUE, None)
        self._attr_native_value = time(
            seconds // 3600, (seconds % 3600) // 60, seconds % 60
        )
        _LOGGER.debug("Updated, new value: %s", self._attr_native_value)


BSH_TIME_SETTINGS = (
    HomeConnectTimeEntityDescription(
        key="BSH.Common.Setting.AlarmClock",
    ),
)
