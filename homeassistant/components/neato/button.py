"""Support for Neato buttons."""
from __future__ import annotations

import logging

from pybotvac import Robot

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NEATO_DOMAIN, NEATO_ROBOTS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Neato button from config entry."""
    dev = []

    for robot in hass.data[NEATO_ROBOTS]:
        dev.append(NeatoDismissAlertButton(robot))

    if not dev:
        return

    _LOGGER.debug("Adding vacuum buttons %s", dev)
    async_add_entities(dev, True)


class NeatoDismissAlertButton(ButtonEntity):
    """Representation of a dismiss_alert button entity."""

    def __init__(
        self,
        robot: Robot,
    ) -> None:
        """Initialize a dismiss_alert Neato button entity."""
        self.robot = robot
        self._button_name = f"{self.robot.name} Dismiss Alert"
        self._robot_serial: str = self.robot.serial

    async def async_press(self) -> None:
        """Press the button."""
        await self.hass.async_add_executor_job(self.robot.dismiss_current_alert)

    @property
    def name(self) -> str:
        """Return the name of this camera."""
        return self._button_name

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return self._robot_serial

    @property
    def entity_category(self) -> EntityCategory:
        """Device entity category."""
        return EntityCategory.CONFIG

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for neato robot."""
        return DeviceInfo(identifiers={(NEATO_DOMAIN, self._robot_serial)})
