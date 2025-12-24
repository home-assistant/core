"""Support for Vera devices."""

from __future__ import annotations

import logging
from typing import Any

import pyvera as veraApi

from homeassistant.const import (
    ATTR_ARMED,
    ATTR_BATTERY_LEVEL,
    ATTR_LAST_TRIP_TIME,
    ATTR_TRIPPED,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from homeassistant.util.dt import utc_from_timestamp

from .common import ControllerData
from .const import CONF_LEGACY_UNIQUE_ID, DOMAIN, VERA_ID_FORMAT

_LOGGER = logging.getLogger(__name__)


class VeraEntity[_DeviceTypeT: veraApi.VeraDevice](Entity):
    """Representation of a Vera device entity."""

    _attr_has_entity_name = True

    def __init__(
        self, vera_device: _DeviceTypeT, controller_data: ControllerData
    ) -> None:
        """Initialize the device."""
        self.vera_device = vera_device
        self.controller = controller_data.controller
        self.controller_data = controller_data

        self._name = self.vera_device.name
        # Append device id to prevent name clashes in HA.
        self.vera_id = VERA_ID_FORMAT.format(
            slugify(vera_device.name), vera_device.vera_device_id
        )

        if controller_data.config_entry.data.get(CONF_LEGACY_UNIQUE_ID):
            self._unique_id = str(self.vera_device.vera_device_id)
        else:
            self._unique_id = f"vera_{controller_data.config_entry.unique_id}_{self.vera_device.vera_device_id}"

        # Set up device info for device registry
        if controller_data.hub:
            self._attr_device_info = DeviceInfo(
                identifiers={
                    (
                        DOMAIN,
                        f"{controller_data.hub.hub_id}_{self.vera_device.vera_device_id}",
                    )
                },
                name=self.vera_device.name,
                manufacturer=self._get_manufacturer(),
                model=self._get_model(),
                via_device=(DOMAIN, controller_data.hub.hub_id),
            )

    def _get_manufacturer(self) -> str:
        """Get the manufacturer name for the device."""
        # Map Vera category to manufacturer, default to generic
        category_manufacturers = {
            veraApi.CATEGORY_DIMMER: "Vera",
            veraApi.CATEGORY_SWITCH: "Vera",
            veraApi.CATEGORY_THERMOSTAT: "Vera",
            veraApi.CATEGORY_LOCK: "Vera",
            veraApi.CATEGORY_CURTAIN: "Vera",
        }
        return category_manufacturers.get(
            getattr(self.vera_device, "category", None), "Vera"
        )

    def _get_model(self) -> str:
        """Get the model name for the device."""
        # Map Vera category to a human-readable model name
        category_models = {
            veraApi.CATEGORY_DIMMER: "Dimmer Switch",
            veraApi.CATEGORY_SWITCH: "On/Off Switch",
            veraApi.CATEGORY_TEMPERATURE_SENSOR: "Temperature Sensor",
            veraApi.CATEGORY_LIGHT_SENSOR: "Light Sensor",
            veraApi.CATEGORY_HUMIDITY_SENSOR: "Humidity Sensor",
            veraApi.CATEGORY_POWER_METER: "Power Meter",
            veraApi.CATEGORY_THERMOSTAT: "Thermostat",
            veraApi.CATEGORY_LOCK: "Door Lock",
            veraApi.CATEGORY_CURTAIN: "Window Covering",
            veraApi.CATEGORY_GARAGE_DOOR: "Garage Door",
            veraApi.CATEGORY_GENERIC: "Generic Device",
            veraApi.CATEGORY_SCENE_CONTROLLER: "Scene Controller",
            veraApi.CATEGORY_ARMABLE: "Armable Device",
            veraApi.CATEGORY_SENSOR: "Sensor",
            veraApi.CATEGORY_UV_SENSOR: "UV Sensor",
            veraApi.CATEGORY_REMOTE: "Remote Control",
        }
        category = getattr(self.vera_device, "category", None)
        if category in category_models:
            return category_models[category]
        # Fallback to category name if available
        category_name = getattr(self.vera_device, "category_name", None)
        return category_name if category_name else "Vera Device"

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.controller.register(self.vera_device, self._update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from updates."""
        self.controller.unregister(self.vera_device, self._update_callback)

    def _update_callback(self, _device: _DeviceTypeT) -> None:
        """Update the state."""
        self.schedule_update_ha_state(True)

    def update(self) -> None:
        """Force a refresh from the device if the device is unavailable."""
        refresh_needed = self.vera_device.should_poll or not self.available
        _LOGGER.debug("%s: update called (refresh=%s)", self._name, refresh_needed)
        if refresh_needed:
            self.vera_device.refresh()

    @property
    def name(self) -> str | None:
        """Return the name of the device.

        When has_entity_name is True, returning None means the entity will use
        the device name. We return None for the main entity and a specific name
        for additional entities if needed.
        """
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attr = {}

        if self.vera_device.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self.vera_device.battery_level

        if self.vera_device.is_armable:
            armed = self.vera_device.is_armed
            attr[ATTR_ARMED] = "True" if armed else "False"

        if self.vera_device.is_trippable:
            if (last_tripped := self.vera_device.last_trip) is not None:
                utc_time = utc_from_timestamp(int(last_tripped))
                attr[ATTR_LAST_TRIP_TIME] = utc_time.isoformat()
            else:
                attr[ATTR_LAST_TRIP_TIME] = None
            tripped = self.vera_device.is_tripped
            attr[ATTR_TRIPPED] = "True" if tripped else "False"

        attr["Vera Device Id"] = self.vera_device.vera_device_id

        return attr

    @property
    def available(self) -> bool:
        """If device communications have failed return false."""
        return not self.vera_device.comm_failure

    @property
    def unique_id(self) -> str:
        """Return a unique ID.

        The Vera assigns a unique and immutable ID number to each device.
        """
        return self._unique_id
