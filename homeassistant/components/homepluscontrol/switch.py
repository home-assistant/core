"""Legrand Home+ Control Switch Entity Module that uses the HomeAssistant DataUpdateCoordinator."""
from datetime import timedelta
import logging

import async_timeout

from homeassistant.components.switch import (
    DEVICE_CLASS_OUTLET,
    DEVICE_CLASS_SWITCH,
    SwitchEntity,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, HW_TYPE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Legrand Home+ Control Switch platform in HomeAssistant.

    Args:
        hass (HomeAssistant): HomeAssistant core object.
        entry (ConfigEntry): ConfigEntry object that configures this platform.
        async_add_entities (function): Function called to add entities of this platform.
    """
    # API object stored here by __init__.py
    api = hass.data[DOMAIN][entry.entry_id]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                return await api.fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="switch",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=60),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    async_add_entities(
        HomeControlSwitchEntity(coordinator, idx)
        for idx, ent in enumerate(coordinator.data)
    )
    _LOGGER.debug("hass.data[%s]: %s", DOMAIN, hass.data[DOMAIN])


class HomeControlSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Entity that represents a Legrand Home+ Control switch.

    It extends the HomeAssistant-provided classes of the CoordinatorEntity and the SwitchEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    The SwitchEntity class provides the functionality of a ToggleEntity and additional power consumption
    methods and state attributes.
    """

    def __init__(self, coordinator, idx):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.idx = idx

    @property
    def name(self):
        """Name of the device."""
        return self.coordinator.data[self.idx].name

    @property
    def unique_id(self):
        """ID (unique) of the device."""
        return self.coordinator.data[self.idx].id

    @property
    def device_info(self):
        """Device information."""
        return {
            "identifiers": {
                # Unique identifiers within the domain
                (DOMAIN, self.unique_id)
            },
            "name": self.name,
            "manufacturer": "Legrand",
            "model": HW_TYPE.get(self.coordinator.data[self.idx].hw_type, "Unknown"),
            "sw_version": self.coordinator.data[self.idx].fw,
        }

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        if self.coordinator.data[self.idx].device == "plug":
            return DEVICE_CLASS_OUTLET
        return DEVICE_CLASS_SWITCH

    @property
    def logger(self) -> logging.Logger:
        """Logger of entity."""
        return logging.getLogger(__name__)

    @property
    def is_on(self):
        """Return entity state."""
        self.logger.debug(
            "Status of "
            + str(self.name)
            + ":"
            + str(self.coordinator.data[self.idx].status)
        )
        return self.coordinator.data[self.idx].status == "on"

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        # Do the turning on.
        await self.coordinator.data[self.idx].turn_on()
        # Update the data
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.coordinator.data[self.idx].turn_off()
        # Update the data
        await self.coordinator.async_request_refresh()
