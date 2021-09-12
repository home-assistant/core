"""AVM FRITZ!Box connectivity sensor."""
from __future__ import annotations

import logging
from typing import Any

from fritzconnection.core.exceptions import FritzConnectionException
from fritzconnection.lib.fritzstatus import FritzStatus

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PLUG,
    DEVICE_CLASS_UPDATE,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import FritzBoxBaseEntity, FritzBoxTools
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


SENSOR_TYPES = (
    BinarySensorEntityDescription(
        key="is_connected",
        name="Connection",
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="is_linked",
        name="Link",
        device_class=DEVICE_CLASS_PLUG,
    ),
    BinarySensorEntityDescription(
        key="firmware_update",
        name="Firmware Update",
        device_class=DEVICE_CLASS_UPDATE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up FRITZ!Box binary sensors")
    fritzbox_tools: FritzBoxTools = hass.data[DOMAIN][entry.entry_id]

    if (
        not fritzbox_tools.connection
        or "WANIPConn1" not in fritzbox_tools.connection.services
    ):
        # Only routers are supported at the moment
        return

    entities = []
    for sensor_type in SENSOR_TYPES:
        entities.append(FritzBoxBinarySensor(fritzbox_tools, entry.title, sensor_type))

    if entities:
        async_add_entities(entities, True)


class FritzBoxBinarySensor(FritzBoxBaseEntity, BinarySensorEntity):
    """Define FRITZ!Box connectivity class."""

    def __init__(
        self,
        fritzbox_tools: FritzBoxTools,
        device_friendly_name: str,
        sensor_type: BinarySensorEntityDescription,
    ) -> None:
        """Init FRITZ!Box connectivity class."""
        self.entity_description: BinarySensorEntityDescription = sensor_type
        self._attr_device_class = self.entity_description.device_class
        self._attr_name = f"{device_friendly_name} {self.entity_description.name}"
        self._attr_unique_id = (
            f"{fritzbox_tools.unique_id}-{self.entity_description.key}"
        )
        super().__init__(fritzbox_tools, device_friendly_name)

    def update(self) -> None:
        """Update data."""
        _LOGGER.debug("Updating FRITZ!Box binary sensors")

        try:
            status: FritzStatus = self._fritzbox_tools.fritz_status
            userinferface_x_avm: dict[
                str, Any
            ] = self._fritzbox_tools.connection.call_action(
                "UserInterface", "X_AVM-DE_GetInfo"
            )
            userinferface1: dict[
                str, Any
            ] = self._fritzbox_tools.connection.call_action("UserInterface1", "GetInfo")
            self._attr_available = True
        except FritzConnectionException:
            _LOGGER.error("Error getting the state from the FRITZ!Box", exc_info=True)
            self._attr_available = False
            return

        if self.entity_description.key == "is_connected":
            self._attr_is_on = bool(status.is_connected)
        elif self.entity_description.key == "is_linked":
            self._attr_is_on = bool(status.is_linked)
        elif self.entity_description.key == "firmware_update":
            latest_fw = userinferface1["NewX_AVM-DE_Version"]
            installed_fw = userinferface_x_avm["NewX_AVM-DE_CurrentFwVersion"]
            self._attr_is_on = userinferface1["NewUpgradeAvailable"]
            self._attr_extra_state_attributes = {
                "installed_version": installed_fw,
                "latest_available_version:": latest_fw,
            }
