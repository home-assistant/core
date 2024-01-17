"""Gaposa cover entity."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from pygaposa import Motor

# These constants are relevant to the type of entity we are using.
# See below for how they are used.
from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MOTION_DELAY
from .coordinator import DataUpdateCoordinatorGaposa

_LOGGER = logging.getLogger(__name__)


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add cover for passed config_entry in HA."""
    # The hub and coordinator are loaded from the associated hass.data entry that was created in the
    # __init__.async_setup_entry function
    gaposa, coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Add all entities to HA
    async_add_entities(
        GaposaCover(coordinator, id, motor) for id, motor in coordinator.data.items()
    )


# This entire class could be written to extend a base class to ensure common attributes
# are kept identical/in sync. It's broken apart here between the Cover and Sensors to
# be explicit about what is returned, and the comments outline where the overlap is.
class GaposaCover(CoordinatorEntity, CoverEntity):
    """Representation of a Gaposa Cover."""

    _attr_device_class = CoverDeviceClass.SHADE

    # The supported features of a cover are done using a bitmask. Using the constants
    # imported above, we can tell HA the features that are supported by this entity.
    # If the supported features were dynamic (ie: different depending on the external
    # device it connected to), then this should be function with an @property decorator.
    supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(
        self, coordinator: DataUpdateCoordinatorGaposa, coverid: str, motor: Motor
    ) -> None:
        """Initialize the motor."""

        super().__init__(coordinator, context=id)

        # Usual setup is done here.
        self.id = coverid
        self.motor = motor
        self.lastCommand: str | None = None
        self.lastCommandTime: datetime | None = None

        # A unique_id for this entity with in this domain. This means for example if you
        # have a sensor on this cover, you must ensure the value returned is unique,
        # which is done here by appending "_cover". For more information, see:
        # https://developers.home-assistant.io/docs/entity_registry_index/#unique-id-requirements
        # Note: This is NOT used to generate the user visible Entity ID used in automations.
        self._attr_unique_id = self.id

        # This is the name for this *entity*, the "name" attribute from "device_info"
        # is used as the device name for device screens in the UI. This name is used on
        # entity screens, and used to build the Entity ID that's used is automations etc.
        self._attr_name = self.motor.name

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        # Importantly for a push integration, the module that will be getting updates
        # needs to notify HA of changes. The dummy device has a registercallback
        # method, so to this we add the 'self.async_write_ha_state' method, to be
        # called where ever there are changes.
        # The call back registration is done once this entity is registered with HA
        # (rather than in the __init__)
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        # self._roller.remove_callback(self.async_write_ha_state)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.info(
            f"_handle_coordinator_update for {self.motor.name} {self.motor.state}"
        )
        self.async_write_ha_state()

    # Information about the devices that is partially visible in the UI.
    # The most critical thing here is to give this entity a name so it is displayed
    # as a "device" in the HA UI. This name is used on the Devices overview table,
    # and the initial screen when the device is added (rather than the entity name
    # property below). You can then associate other Entities (eg: a battery
    # sensor) with this device, so it shows more like a unified element in the UI.
    # For example, an associated battery sensor will be displayed in the right most
    # column in the Configuration > Devices view for a device.
    # To associate an entity with this device, the device_info must also return an
    # identical "identifiers" attribute, but not return a name attribute.
    # See the sensors.py file for the corresponding example setup.
    # Additional meta data can also be returned here, including sw_version (displayed
    # as Firmware), model and manufacturer (displayed as <model> by <manufacturer>)
    # shown on the device info screen. The Manufacturer and model also have their
    # respective columns on the Devices overview table. Note: Many of these must be
    # set when the device is first added, and they are not always automatically
    # refreshed by HA from it's internal cache.
    # For more information see:
    # https://developers.home-assistant.io/docs/device_registry_index/#device-properties
    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self.id)},
            # If desired, the name for the device could be different to the entity
            "name": self.motor.name,
            "manufacturer": "Gaposa",
        }

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
    @property
    def available(self) -> bool:
        """Return True if roller and hub is available."""
        return True

    # The following properties are how HA knows the current state of the device.
    # These must return a value from memory, not make a live query to the device/hub
    # etc when called (hence they are properties). For a push based integration,
    # HA is notified of changes via the async_write_ha_state call. See the __init__
    # method for hos this is implemented in this example.
    # The properties that are expected for a cover are based on the supported_features
    # property of the object. In the case of a cover, see the following for more
    # details: https://developers.home-assistant.io/docs/core/entity/cover/

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed, same as position 0."""
        return (
            True
            if self.motor.state == "DOWN"
            else False
            if self.motor.state == "UP"
            else None
        )

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self.is_moving and self.lastCommand == "DOWN"

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self.is_moving and self.lastCommand == "UP"

    @property
    def is_moving(self) -> bool:
        """Return if the cover is moving or not."""
        if self.lastCommandTime is not None and self.lastCommand != "STOP":
            now = datetime.now()
            complete = self.lastCommandTime + timedelta(seconds=MOTION_DELAY)
            return now < complete
        return False

    # These methods allow HA to tell the actual device what to do. In this case, move
    # the cover to the desired position, or open and close it all the way.
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self.lastCommand = "UP"
        self.lastCommandTime = datetime.now()
        await self.motor.up(False)
        self.schedule_refresh_ha_after_motion()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self.lastCommand = "DOWN"
        self.lastCommandTime = datetime.now()
        await self.motor.down(False)
        self.schedule_refresh_ha_after_motion()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self.lastCommand = "STOP"
        self.lastCommandTime = datetime.now()
        await self.motor.stop(False)

    def schedule_refresh_ha_after_motion(self) -> None:
        """Wait for the cover to stop moving and update HA state."""
        self.hass.async_create_task(self.refresh_ha_after_motion())

    async def refresh_ha_after_motion(self) -> None:
        """Refresh after a delay."""
        await asyncio.sleep(MOTION_DELAY)
        _LOGGER.info(f"delayed_refresh for {self.motor.name} {self.motor.state}")
        self.async_write_ha_state()
