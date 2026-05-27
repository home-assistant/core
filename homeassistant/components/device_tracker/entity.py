"""Provide functionality to keep track of devices."""

import asyncio
from typing import TYPE_CHECKING, Any, final

from propcache.api import cached_property

from homeassistant.components import zone
from homeassistant.components.zone import ATTR_PASSIVE, ATTR_RADIUS
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_HOME,
    STATE_NOT_HOME,
    EntityCategory,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import (
    DeviceInfo,
    EventDeviceRegistryUpdatedData,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.hass_dict import HassKey

from .const import (
    ATTR_HOST_NAME,
    ATTR_IN_ZONES,
    ATTR_IP,
    ATTR_MAC,
    ATTR_SOURCE_TYPE,
    CONF_ASSOCIATED_ZONE,
    CONNECTED_DEVICE_REGISTERED,
    DOMAIN,
    LOGGER,
    SourceType,
)

DATA_KEY: HassKey[dict[str, tuple[str, str]]] = HassKey(f"{DOMAIN}_mac")


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
    mac = dr.format_mac(mac)
    if DATA_KEY in hass.data:
        hass.data[DATA_KEY][mac] = (domain, unique_id)
        return

    # Setup listening.

    # dict mapping mac -> partial unique ID
    data = hass.data[DATA_KEY] = {mac: (domain, unique_id)}

    @callback
    def handle_device_event(ev: Event[EventDeviceRegistryUpdatedData]) -> None:
        """Enable the online status entity for the mac of a newly created device."""
        # Only for new devices
        if ev.data["action"] != "create":
            return

        dev_reg = dr.async_get(hass)
        device_entry = dev_reg.async_get(ev.data["device_id"])

        if device_entry is None:
            # This should not happen, since the device was just created.
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

        entity_entry = ent_reg.entities[entity_id]

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
    """Represent a tracked device.

    Not intended to be directly inherited by integrations. Integrations should
    inherit TrackerEntity, BaseScannerEntity or ScannerEntity instead.
    """

    _attr_device_info: None = None
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_source_type: SourceType

    @cached_property
    def battery_level(self) -> int | None:
        """Return the battery level of the device.

        Percentage from 0-100.
        """
        return None

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        if hasattr(self, "_attr_source_type"):
            return self._attr_source_type
        raise NotImplementedError

    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attr: dict[str, Any] = {ATTR_SOURCE_TYPE: self.source_type}

        if self.battery_level is not None:
            attr[ATTR_BATTERY_LEVEL] = self.battery_level

        return attr


class TrackerEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes tracker entities."""


CACHED_TRACKER_PROPERTIES_WITH_ATTR_ = {
    "in_zones",
    "latitude",
    "location_accuracy",
    "location_name",
    "longitude",
}


class TrackerEntity(
    BaseTrackerEntity, cached_properties=CACHED_TRACKER_PROPERTIES_WITH_ATTR_
):
    """Base class for a tracked device."""

    entity_description: TrackerEntityDescription
    _attr_in_zones: list[str] | None = None
    _attr_latitude: float | None = None
    _attr_location_accuracy: float = 0
    _attr_location_name: str | None = None
    _attr_longitude: float | None = None
    _attr_source_type: SourceType = SourceType.GPS

    __active_zone: State | None = None
    __in_zones: list[str] | None = None

    @cached_property
    def should_poll(self) -> bool:
        """No polling for entities that have location pushed."""
        return False

    @property
    def force_update(self) -> bool:
        """All updates need to be written to the state machine if we're not polling."""
        return not self.should_poll

    @cached_property
    def in_zones(self) -> list[str] | None:
        """Return the entity_id of zones the device is currently in.

        The list may be in any order; the base class sorts it by zone radius
        and discards zones which do not exist. Takes precedence over latitude
        and longitude when set (including when set to an empty list).
        """
        return self._attr_in_zones

    @cached_property
    def location_accuracy(self) -> float:
        """Return the location accuracy of the device.

        Value in meters.
        """
        return self._attr_location_accuracy

    @cached_property
    def location_name(self) -> str | None:
        """Return a location name for the current location of the device."""
        return self._attr_location_name

    @cached_property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self._attr_latitude

    @cached_property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self._attr_longitude

    @callback
    def _async_write_ha_state(self) -> None:
        """Calculate active zones."""
        if (zones := self.in_zones) is not None:
            zone_states = sorted(
                (
                    zone_state
                    for entity_id in zones
                    if (zone_state := self.hass.states.get(entity_id)) is not None
                ),
                key=lambda z: z.attributes[ATTR_RADIUS],
            )
            self.__active_zone = next(
                (z for z in zone_states if not z.attributes.get(ATTR_PASSIVE)),
                None,
            )
            self.__in_zones = [z.entity_id for z in zone_states]
        elif (
            self.available and self.latitude is not None and self.longitude is not None
        ):
            self.__active_zone, self.__in_zones = zone.async_in_zones(
                self.hass, self.latitude, self.longitude, self.location_accuracy
            )
        else:
            self.__active_zone = None
            self.__in_zones = None
        super()._async_write_ha_state()

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        if self.location_name is not None:
            return self.location_name

        if (
            self.latitude is not None and self.longitude is not None
        ) or self.__in_zones is not None:
            zone_state = self.__active_zone
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
    def state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attr: dict[str, Any] = {ATTR_IN_ZONES: self.__in_zones or []}
        attr.update(super().state_attributes)

        if self.latitude is not None and self.longitude is not None:
            attr[ATTR_LATITUDE] = self.latitude
            attr[ATTR_LONGITUDE] = self.longitude
            attr[ATTR_GPS_ACCURACY] = self.location_accuracy

        return attr


class BaseScannerEntity(BaseTrackerEntity):
    """Base class for a tracked device that can be connected or disconnected.

    Unlike ScannerEntity, this entity does not make assumptions about MAC
    addresses being used to identify the device.
    """

    _scanner_option_associated_zone: str = zone.ENTITY_ID_HOME
    _scanner_option_associated_zone_unsub: CALLBACK_TYPE | None = None

    async def async_internal_added_to_hass(self) -> None:
        """Call when the scanner entity is added to hass."""
        await super().async_internal_added_to_hass()
        if not self.registry_entry:
            return
        self._async_read_entity_options()

    async def async_internal_will_remove_from_hass(self) -> None:
        """Call when the scanner entity is about to be removed from hass."""
        await super().async_internal_will_remove_from_hass()
        if not self.registry_entry:
            return
        if self._scanner_option_associated_zone_unsub is not None:
            self._scanner_option_associated_zone_unsub()
            self._scanner_option_associated_zone_unsub = None
        self._async_clear_associated_zone_issue()

    @callback
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated."""
        self._async_read_entity_options()

    @callback
    def _async_read_entity_options(self) -> None:
        """Read entity options from the entity registry.

        Called when the entity registry entry has been updated and before the
        scanner entity is added to the state machine.
        """
        assert self.registry_entry
        if (scanner_options := self.registry_entry.options.get(DOMAIN)) and (
            associated_zone := scanner_options.get(CONF_ASSOCIATED_ZONE)
        ):
            new_zone = associated_zone
        else:
            new_zone = zone.ENTITY_ID_HOME

        if new_zone == self._scanner_option_associated_zone:
            return

        # Tear down tracking for the previous zone.
        if self._scanner_option_associated_zone_unsub is not None:
            self._scanner_option_associated_zone_unsub()
            self._scanner_option_associated_zone_unsub = None
        self._async_clear_associated_zone_issue()

        self._scanner_option_associated_zone = new_zone

        # zone.home is always present so no tracking or issue handling needed.
        if new_zone == zone.ENTITY_ID_HOME:
            return

        self._scanner_option_associated_zone_unsub = async_track_state_change_event(
            self.hass, new_zone, self._async_associated_zone_state_changed
        )
        if self.hass.states.get(new_zone) is None:
            self._async_create_associated_zone_issue()

    @callback
    def _async_associated_zone_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Open or clear the repair issue when the associated zone appears or disappears."""
        if event.data["new_state"] is None:
            self._async_create_associated_zone_issue()
        else:
            self._async_clear_associated_zone_issue()
        self.async_write_ha_state()

    @callback
    def _async_create_associated_zone_issue(self) -> None:
        """Create a repair issue prompting the user to reconfigure the scanner."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self._associated_zone_issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="associated_zone_missing",
            translation_placeholders={
                "entity_id": self.entity_id,
                "zone": self._scanner_option_associated_zone,
            },
        )

    @callback
    def _async_clear_associated_zone_issue(self) -> None:
        """Clear the associated-zone-missing repair issue if it exists."""
        ir.async_delete_issue(self.hass, DOMAIN, self._associated_zone_issue_id)

    @property
    def _associated_zone_issue_id(self) -> str:
        """Return the issue id for the associated-zone-missing repair."""
        if TYPE_CHECKING:
            assert self.registry_entry
        return f"associated_zone_missing_{self.registry_entry.id}"

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        if self.is_connected is None:
            return None
        if not self.is_connected:
            return STATE_NOT_HOME
        associated_zone = self._scanner_option_associated_zone
        if associated_zone == zone.ENTITY_ID_HOME:
            return STATE_HOME
        if zone_state := self.hass.states.get(associated_zone):
            return zone_state.name
        # Configured zone has been removed; state is unknown.
        return None

    @property
    def is_connected(self) -> bool | None:
        """Return true if the device is connected."""
        raise NotImplementedError

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attr: dict[str, Any] = {ATTR_IN_ZONES: []}
        attr.update(super().state_attributes)

        if not self.is_connected:
            return attr

        associated_zone = self._scanner_option_associated_zone
        # If the configured zone has been removed, in_zones stays empty so the
        # attribute does not claim membership in a zone that no longer exists.
        if (
            associated_zone != zone.ENTITY_ID_HOME
            and self.hass.states.get(associated_zone) is None
        ):
            return attr

        attr[ATTR_IN_ZONES] = [
            associated_zone,
            *zone.async_get_enclosing_zones(self.hass, associated_zone),
        ]

        return attr


class ScannerEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes tracker entities."""


CACHED_SCANNER_PROPERTIES_WITH_ATTR_ = {
    "ip_address",
    "mac_address",
    "hostname",
}


class ScannerEntity(
    BaseScannerEntity, cached_properties=CACHED_SCANNER_PROPERTIES_WITH_ATTR_
):
    """Base class for a tracked device that is on a scanned network."""

    entity_description: ScannerEntityDescription
    _attr_hostname: str | None = None
    _attr_ip_address: str | None = None
    _attr_mac_address: str | None = None
    _attr_source_type: SourceType = SourceType.ROUTER

    @cached_property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._attr_ip_address

    @cached_property
    def mac_address(self) -> str | None:
        """Return the mac address of the device."""
        return self._attr_mac_address

    @cached_property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return self._attr_hostname

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
            if self.is_connected and self.ip_address:
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
            connections={(dr.CONNECTION_NETWORK_MAC, self.mac_address)}
        )

    async def async_internal_added_to_hass(self) -> None:
        """Handle added to Home Assistant."""
        # Entities without a unique ID don't have a device
        if (
            not self.registry_entry
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

    # BaseScannerEntity.state_attributes is @final to keep external subclasses
    # from tampering with it; ScannerEntity is an in-tree subclass that
    # intentionally extends it with ip/mac/hostname.
    @final  # type: ignore[misc]
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attr = super().state_attributes

        if ip_address := self.ip_address:
            attr[ATTR_IP] = ip_address
        if (mac_address := self.mac_address) is not None:
            attr[ATTR_MAC] = mac_address
        if (hostname := self.hostname) is not None:
            attr[ATTR_HOST_NAME] = hostname

        return attr
