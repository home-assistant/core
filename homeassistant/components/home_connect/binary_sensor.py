"""Provides a binary sensor for Home Connect."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_VALUE, DOMAIN
from .entity import HomeConnectEntity, HomeConnectEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect binary sensor."""

    def get_entities():
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        return [
            HomeConnectBinarySensorEntity(device, state)
            for state in BSH_BINARY_SENSORS
            for device in hc_api.devices
            if state.key in device.appliance.status
        ]

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectBinarySensorEntityDescription(
    HomeConnectEntityDescription,
    BinarySensorEntityDescription,
    frozen_or_thawed=True,
):
    """Description of a Home Connect binary sensor entity."""


class HomeConnectBinarySensorEntity(HomeConnectEntity, BinarySensorEntity):
    """Binary sensor for Home Connect."""

    entity_description: HomeConnectBinarySensorEntityDescription

    @property
    def available(self) -> bool:
        """Return true if the binary sensor is available."""
        return self.is_on is not None

    async def async_update(self) -> None:
        """Update the binary sensor's status."""
        if (
            not self.status
            or ATTR_VALUE not in self.status
            or self.status[ATTR_VALUE] not in [True, False]
        ):
            self._attr_is_on = None
            return
        self._attr_is_on = self.status[ATTR_VALUE]
        _LOGGER.debug("Updated, new state: %s", self._attr_is_on)


BSH_BINARY_SENSORS = (
    HomeConnectBinarySensorEntityDescription(
        key="BSH.Common.Status.RemoteControlActive",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="BSH.Common.Status.RemoteControlStartAllowed",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="BSH.Common.Status.LocalControlActive",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="ConsumerProducts.CleaningRobot.Status.DustBoxInserted",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="ConsumerProducts.CleaningRobot.Status.Lifted",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="ConsumerProducts.CleaningRobot.Status.Lost",
    ),
)
