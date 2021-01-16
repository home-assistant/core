"""Legrand Home+ Control Switch Entity Module that uses the HomeAssistant DataUpdateCoordinator."""
from datetime import timedelta
import logging

import async_timeout

from homeassistant.components.switch import (
    DEVICE_CLASS_OUTLET,
    DEVICE_CLASS_SWITCH,
    SwitchEntity,
)

# from homeassistant.helpers import entity_platform
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, HW_TYPE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Legrand Home+ Control Switch platform in HomeAssistant.

    Args:
        hass (HomeAssistant): HomeAssistant core object.
        config_entry (ConfigEntry): ConfigEntry object that configures this platform.
        async_add_entities (function): Function called to add entities of this platform.
    """
    # Dictionaty of entities of this integration
    hass.data[DOMAIN]["entities"] = {}

    # API object stored here by __init__.py
    api = hass.data[DOMAIN][config_entry.entry_id]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        switch_data = {}
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                switch_data = await api.fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err} [{type(err)}]")

        # Remove obsolete entities from the Entity and Device Registries
        if coordinator.data and len(coordinator.data.keys()) > 0:
            for id, ent in coordinator.data.items():
                _LOGGER.debug("Coordinator item: " + str(id) + ": " + str(ent))

        device_reg = await hass.helpers.device_registry.async_get_registry()

        for ent_id, ent in api.switches_to_remove.items():
            r_entity = hass.data[DOMAIN]["entities"].pop(ent_id, None)
            if r_entity is None:
                _LOGGER.debug(
                    "Entity %s was marked from deletion, but is not registered by the integration.",
                    str(ent),
                )
                continue
            _LOGGER.debug(
                "Remove entity %s [device: %s] from HA registries.",
                r_entity.entity_id,
                r_entity.registry_entry.device_id,
            )
            device_reg.async_remove_device(r_entity.registry_entry.device_id)
            await r_entity.async_remove()

        # Reset the api object dictionary of deleted elements
        api.switches_to_remove = {}

        # Add entities to HomeAssistant domain and registries
        new_entities = []
        for idx, switch in switch_data.items():
            if idx not in hass.data[DOMAIN]["entities"]:
                hass.data[DOMAIN]["entities"][idx] = HomeControlSwitchEntity(
                    coordinator, idx
                )
                new_entities.append(hass.data[DOMAIN]["entities"][idx])

        async_add_entities(new_entities)

        return switch_data

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
    hass.data[DOMAIN][config_entry.entry_id + "_coordinator"] = coordinator

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    _LOGGER.debug("hass.data[%s]: %s", DOMAIN, hass.data[DOMAIN])
    await view_data(hass)


async def view_data(hass):
    """Debug relevant Hass objects."""
    device_reg = await hass.helpers.device_registry.async_get_registry()
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    for ent in entity_reg.entities:
        _LOGGER.debug("Entity registry entity: %s", str(ent))
    for dev in device_reg.devices:
        _LOGGER.debug("Device registry device: %s", str(dev))


class HomeControlSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Entity that represents a Legrand Home+ Control switch.

    It extends the HomeAssistant-provided classes of the CoordinatorEntity and the SwitchEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass

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
    def available(self) -> bool:
        """Return if entity is available.

        This is the case when the coordinator is able to update the data successfully
        AND the switch entity is reachable.

        This method overrides the one of the CoordinatorEntity
        """
        return (
            self.coordinator.last_update_success
            and self.coordinator.data[self.idx].reachable
        )

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

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self.registry_entry is not None:
            entity_reg = (
                await self.coordinator.hass.helpers.entity_registry.async_get_registry()
            )
            entity_reg.async_remove(self.registry_entry.entity_id)
