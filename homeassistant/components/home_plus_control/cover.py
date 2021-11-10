"""Legrand Home+ Control Cover Entity Module that uses the HomeAssistant DataUpdateCoordinator."""
from functools import partial

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_SHUTTER,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.core import callback
from homeassistant.helpers import dispatcher
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DISPATCHER_REMOVERS, DOMAIN, HW_TYPE, SIGNAL_ADD_ENTITIES


@callback
def add_cover_entities(new_unique_ids, coordinator, add_entities):
    """Add cover entities to the platform.

    Args:
        new_unique_ids (set): Unique identifiers of entities to be added to Home Assistant.
        coordinator (DataUpdateCoordinator): Data coordinator of this platform.
        add_entities (function): Method called to add entities to Home Assistant.
    """
    new_entities = [
        HomeControlCoverEntity(coordinator, uid)
        for uid in new_unique_ids
        if coordinator.data[uid].device == "automation"
    ]
    add_entities(new_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Legrand Home+ Control Cover platform in HomeAssistant.

    Args:
        hass (HomeAssistant): HomeAssistant core object.
        config_entry (ConfigEntry): ConfigEntry object that configures this platform.
        async_add_entities (function): Function called to add entities of this platform.
    """
    partial_add_cover_entities = partial(
        add_cover_entities, add_entities=async_add_entities
    )
    # Connect the dispatcher for the cover platform
    hass.data[DOMAIN][config_entry.entry_id][DISPATCHER_REMOVERS].append(
        dispatcher.async_dispatcher_connect(
            hass, SIGNAL_ADD_ENTITIES, partial_add_cover_entities
        )
    )


class HomeControlCoverEntity(CoordinatorEntity, CoverEntity):
    """Entity that represents a Legrand Home+ Control Cover.

    It extends the HomeAssistant-provided classes of the CoordinatorEntity and the CoverEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass

    The CoverEntity class provides all functionalities expected in a cover.
    """

    def __init__(self, coordinator, idx):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.idx = idx
        self.module = self.coordinator.data[self.idx]

    @property
    def name(self):
        """Name of the device."""
        return self.module.name

    @property
    def unique_id(self):
        """ID (unique) of the device."""
        return self.idx

    @property
    def device_info(self) -> DeviceInfo:
        """Device information."""
        return DeviceInfo(
            identifiers={
                # Unique identifiers within the domain
                (DOMAIN, self.unique_id)
            },
            manufacturer="Legrand",
            model=HW_TYPE.get(self.module.hw_type),
            name=self.name,
            sw_version=self.module.fw,
        )

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_SHUTTER

    @property
    def available(self) -> bool:
        """Return if entity is available.

        This is the case when the coordinator is able to update the data successfully
        AND the cover entity is reachable.

        This method overrides the one of the CoordinatorEntity
        """
        return self.coordinator.last_update_success and self.module.reachable

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self.module.close()
        await self.coordinator.async_request_refresh()

    async def async_open_cover(self, **kwargs):
        """Close the cover."""
        await self.module.open()
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self.module.stop()
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs):
        """Move the cover shutter to a specific position."""
        await self.module.set_level(kwargs[ATTR_POSITION])
        await self.coordinator.async_request_refresh()

    @property
    def current_cover_position(self):
        """Return the current position of cover shutter."""
        return self.module.level

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self.module.level == self.module.CLOSED_FULL
