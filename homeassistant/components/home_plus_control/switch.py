"""Legrand Home+ Control Switch Entity Module that uses the HomeAssistant DataUpdateCoordinator."""
from datetime import timedelta
import logging

import async_timeout

from homeassistant.components.switch import (
    DEVICE_CLASS_OUTLET,
    DEVICE_CLASS_SWITCH,
    SwitchEntity,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import dispatcher
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    API,
    DATA_COORDINATOR,
    DOMAIN,
    ENTITY_UIDS,
    HW_TYPE,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_REMOVE_ENTITIES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Legrand Home+ Control Switch platform in HomeAssistant.

    Args:
        hass (HomeAssistant): HomeAssistant core object.
        config_entry (ConfigEntry): ConfigEntry object that configures this platform.
        async_add_entities (function): Function called to add entities of this platform.
    """
    # API object stored here by __init__.py
    api = hass.data[DOMAIN][config_entry.entry_id][API]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                switch_data = await api.fetch_data()
        except HomeAssistantError as err:
            raise UpdateFailed(
                f"Error communicating with API: {err} [{type(err)}]"
            ) from err

        # Send out signal for removal of obsolete entities from Home Assistant
        if len(api.switches_to_remove.keys()) > 0:
            device_registry = hass.helpers.device_registry.async_get(hass)
            dispatcher.async_dispatcher_send(
                hass,
                SIGNAL_REMOVE_ENTITIES,
                api.switches_to_remove.keys(),
                hass.data[DOMAIN][config_entry.entry_id][ENTITY_UIDS],
                device_registry,
            )
            # Reset the api object dictionary of deleted elements
            api.switches_to_remove = {}

        # Send out signal for new entity addition to Home Assistant
        new_entity_uids = []
        for unique_id in switch_data:
            if unique_id not in hass.data[DOMAIN][config_entry.entry_id][ENTITY_UIDS]:
                new_entity_uids.append(unique_id)
        if len(new_entity_uids) > 0:
            dispatcher.async_dispatcher_send(
                hass,
                SIGNAL_ADD_ENTITIES,
                new_entity_uids,
                coordinator,
                async_add_entities,
            )

        return switch_data

    # Register the Data Coordinator with the integration
    coordinator = hass.data[DOMAIN][config_entry.entry_id].get(DATA_COORDINATOR)
    if coordinator is None:
        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="switch",
            update_method=async_update_data,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=60),
        )

        # Add the coordinator to the domain's data in HA
        hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR] = coordinator

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()


class HomeControlSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Entity that represents a Legrand Home+ Control switch.

    It extends the HomeAssistant-provided classes of the CoordinatorEntity and the SwitchEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass

    The SwitchEntity class provides the functionality of a ToggleEntity and additional power
    consumption methods and state attributes.
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
    def device_info(self):
        """Device information."""
        return {
            "identifiers": {
                # Unique identifiers within the domain
                (DOMAIN, self.unique_id)
            },
            "name": self.name,
            "manufacturer": "Legrand",
            "model": HW_TYPE.get(self.module.hw_type),
            "sw_version": self.module.fw,
        }

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        if self.module.device == "plug":
            return DEVICE_CLASS_OUTLET
        return DEVICE_CLASS_SWITCH

    @property
    def available(self) -> bool:
        """Return if entity is available.

        This is the case when the coordinator is able to update the data successfully
        AND the switch entity is reachable.

        This method overrides the one of the CoordinatorEntity
        """
        return self.coordinator.last_update_success and self.module.reachable

    @property
    def is_on(self):
        """Return entity state."""
        return self.module.status == "on"

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        # Do the turning on.
        await self.module.turn_on()
        # Update the data
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.module.turn_off()
        # Update the data
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Register with the integration's entity map
        domain = self.registry_entry.platform
        config_entry_id = self.registry_entry.config_entry_id
        entity_id = self.registry_entry.entity_id
        self.hass.data[domain][config_entry_id][ENTITY_UIDS][self.unique_id] = entity_id
