"""Code to set up a device tracker platform using a config entry."""
from __future__ import annotations

import asyncio
from typing import final

from homeassistant.components import zone
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityCategory
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.typing import StateType

from .const import (
    ATTR_HOST_NAME,
    ATTR_IP,
    ATTR_MAC,
    ATTR_SOURCE_TYPE,
    CONNECTED_DEVICE_REGISTERED,
    DOMAIN,
    LOGGER,
    SourceType,
)

# mypy: disallow-any-generics


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an entry."""
    component: EntityComponent[BaseTrackerEntity] | None = hass.data.get(DOMAIN)

    if component is not None:
        return await component.async_setup_entry(entry)

    component = hass.data[DOMAIN] = EntityComponent[BaseTrackerEntity](
        LOGGER, DOMAIN, hass
    )

    # Clean up old devices created by device tracker entities in the past.
    # Can be removed after 2022.6
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    devices_with_trackers = set()
    devices_with_non_trackers = set()

    for entity in ent_reg.entities.values():
        if entity.device_id is None:
            continue

        if entity.domain == DOMAIN:
            devices_with_trackers.add(entity.device_id)
        else:
            devices_with_non_trackers.add(entity.device_id)

    for device_id in devices_with_trackers - devices_with_non_trackers:
        for entity in er.async_entries_for_device(ent_reg, device_id, True):
            ent_reg.async_update_entity(entity.entity_id, device_id=None)
        dev_reg.async_remove_device(device_id)

    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry."""
    component: EntityComponent[BaseTrackerEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@callback
def _async_connected_device_registered(
    hass: HomeAssistant, mac: str, ip_address: str | None, hostname: str | None
) -> None:
    """Register a newly seen connected device.

    This is currently used by the dhcp integration
    to listen for newly registered connected devices
    for discovery.
    """
    async_dispatcher_send(
        hass,
        CONNECTED_DEVICE_REGISTERED,
        {
            ATTR_IP: ip_address,
            ATTR_MAC: mac,
            ATTR_HOST_NAME: hostname,
        },
    )


@callback
def _async_register_mac(
    hass: HomeAssistant,
    domain: str,
    mac: str,
    unique_id: str,
) -> None:
    """Register a mac address with a unique ID."""
    data_key = "device_tracker_mac"
    mac = dr.format_mac(mac)
    if data_key in hass.data:
        hass.data[data_key][mac] = (domain, unique_id)
        return

    # Setup listening.

    # dict mapping mac -> partial unique ID
    data = hass.data[data_key] = {mac: (domain, unique_id)}

    @callback
    def handle_device_event(ev: Event) -> None:
        """Enable the online status entity for the mac of a newly created device."""
        # Only for new devices
        if ev.data["action"] != "create":
            return

        dev_reg = dr.async_get(hass)
        device_entry = dev_reg.async_get(ev.data["device_id"])

        if device_entry is None:
            return

        # Check if device has a mac
        mac = None
        for conn in device_entry.connections:
            if conn[0] == dr.CONNECTION_NETWORK_MAC:
                mac = conn[1]
                break

        if mac is None:
            return

        # Check if we have an entity for this mac
        if (unique_id := data.get(mac)) is None:
            return

        ent_reg = er.async_get(hass)

        if (entity_id := ent_reg.async_get_entity_id(DOMAIN, *unique_id)) is None:
            return

        if (entity_entry := ent_reg.async_get(entity_id)) is None:
            return

        # Make sure entity has a config entry and was disabled by the
        # default disable logic in the integration and new entities
        # are allowed to be added.
        if (
            entity_entry.config_entry_id is None
            or (
                (
                    config_entry := hass.config_entries.async_get_entry(
                        entity_entry.config_entry_id
                    )
                )
                is not None
                and config_entry.pref_disable_new_entities
            )
            or entity_entry.disabled_by != er.RegistryEntryDisabler.INTEGRATION
        ):
            return

        # Enable entity
        ent_reg.async_update_entity(entity_id, disabled_by=None)

    hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, handle_device_event)


class BaseTrackerEntity(Entity):
    """Represent a tracked device."""

    _attr_device_info: None = None
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device.

        Percentage from 0-100.
        """
        return None

    @property
    def source_type(self) -> SourceType | str:
        """Return the source type, eg gps or router, of the device."""
        raise NotImplementedError

    @property
    def state_attributes(self) -> dict[str, StateType]:
        """Return the device state attributes."""
        attr: dict[str, StateType] = {ATTR_SOURCE_TYPE: self.source_type}

        if self.battery_level is not None:
            attr[ATTR_BATTERY_LEVEL] = self.battery_level

        return attr


class TrackerEntity(BaseTrackerEntity):
    """Base class for a tracked device."""

    @property
    def should_poll(self) -> bool:
        """No polling for entities that have location pushed."""
        return False

    @property
    def force_update(self) -> bool:
        """All updates need to be written to the state machine if we're not polling."""
        return not self.should_poll

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device.

        Value in meters.
        """
        return 0

    @property
    def location_name(self) -> str | None:
        """Return a location name for the current location of the device."""
        return None

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        raise NotImplementedError

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        raise NotImplementedError

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        if self.location_name is not None:
            return self.location_name

        if self.latitude is not None and self.longitude is not None:
            zone_state = zone.async_active_zone(
                self.hass, self.latitude, self.longitude, self.location_accuracy
            )
            if zone_state is None:
                state = STATE_NOT_HOME
            elif zone_state.entity_id == zone.ENTITY_ID_HOME:
                state = STATE_HOME
            else:
                state = zone_state.name
            return state

        return None

    @final
    @property
    def state_attributes(self) -> dict[str, StateType]:
        """Return the device state attributes."""
        attr: dict[str, StateType] = {}
        attr.update(super().state_attributes)

        if self.latitude is not None and self.longitude is not None:
            attr[ATTR_LATITUDE] = self.latitude
            attr[ATTR_LONGITUDE] = self.longitude
            attr[ATTR_GPS_ACCURACY] = self.location_accuracy

        return attr


class ScannerEntity(BaseTrackerEntity):
    """Base class for a tracked device that is on a scanned network."""

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return None

    @property
    def mac_address(self) -> str | None:
        """Return the mac address of the device."""
        return None

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return None

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if self.is_connected:
            return STATE_HOME
        return STATE_NOT_HOME

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        raise NotImplementedError

    @property
    def unique_id(self) -> str | None:
        """Return unique ID of the entity."""
        return self.mac_address

    @final
    @property
    def device_info(self) -> DeviceInfo | None:
        """Device tracker entities should not create device registry entries."""
        return None

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default."""
        # If mac_address is None, we can never find a device entry.
        return (
            # Do not disable if we won't activate our attach to device logic
            self.mac_address is None
            or self.device_info is not None
            # Disable if we automatically attach but there is no device
            or self.find_device_entry() is not None
        )

    @callback
    def add_to_platform_start(
        self,
        hass: HomeAssistant,
        platform: EntityPlatform,
        parallel_updates: asyncio.Semaphore | None,
    ) -> None:
        """Start adding an entity to a platform."""
        super().add_to_platform_start(hass, platform, parallel_updates)
        if self.mac_address and self.unique_id:
            _async_register_mac(
                hass,
                platform.platform_name,
                self.mac_address,
                self.unique_id,
            )
            if self.is_connected:
                _async_connected_device_registered(
                    hass,
                    self.mac_address,
                    self.ip_address,
                    self.hostname,
                )

    @callback
    def find_device_entry(self) -> dr.DeviceEntry | None:
        """Return device entry."""
        assert self.mac_address is not None

        return dr.async_get(self.hass).async_get_device(
            set(), {(dr.CONNECTION_NETWORK_MAC, self.mac_address)}
        )

    async def async_internal_added_to_hass(self) -> None:
        """Handle added to Home Assistant."""
        # Entities without a unique ID don't have a device
        if (
            not self.registry_entry
            or not self.platform
            or not self.platform.config_entry
            or not self.mac_address
            or (device_entry := self.find_device_entry()) is None
            # Entities should not have a device info. We opt them out
            # of this logic if they do.
            or self.device_info
        ):
            if self.device_info:
                LOGGER.debug("Entity %s unexpectedly has a device info", self.entity_id)
            await super().async_internal_added_to_hass()
            return

        # Attach entry to device
        if self.registry_entry.device_id != device_entry.id:
            self.registry_entry = er.async_get(self.hass).async_update_entity(
                self.entity_id, device_id=device_entry.id
            )

        # Attach device to config entry
        if self.platform.config_entry.entry_id not in device_entry.config_entries:
            dr.async_get(self.hass).async_update_device(
                device_entry.id,
                add_config_entry_id=self.platform.config_entry.entry_id,
            )

        # Do this last or else the entity registry update listener has been installed
        await super().async_internal_added_to_hass()

    @final
    @property
    def state_attributes(self) -> dict[str, StateType]:
        """Return the device state attributes."""
        attr: dict[str, StateType] = {}
        attr.update(super().state_attributes)
        if self.ip_address is not None:
            attr[ATTR_IP] = self.ip_address
        if self.mac_address is not None:
            attr[ATTR_MAC] = self.mac_address
        if self.hostname is not None:
            attr[ATTR_HOST_NAME] = self.hostname

        return attr
