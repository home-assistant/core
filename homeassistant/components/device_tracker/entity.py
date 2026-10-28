"""Provide functionality to keep track of devices."""

import logging
from typing import TYPE_CHECKING, Any, final, override

from propcache.api import cached_property

from homeassistant.components import zone
from homeassistant.components.zone import ZoneEntityStateAttribute
from homeassistant.const import (  # noqa: F401
    ATTR_BATTERY_LEVEL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_HOME,
    STATE_NOT_HOME,
    EntityCategory,
    EntityStateAttribute,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    async_get_hass_or_none,
    callback,
)
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import CalculatedState, Entity, EntityDescription
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.loader import async_suggest_report_issue

from .const import (  # noqa: F401
    ATTR_HOST_NAME,
    ATTR_IN_ZONES,
    ATTR_IP,
    ATTR_MAC,
    ATTR_SOURCE_TYPE,
    ATTR_TRACKING_TYPE,
    CONF_ASSOCIATED_ZONE,
    CONNECTED_DEVICE_REGISTERED,
    DOMAIN,
    LOGGER,
    DeviceTrackerEntityCapabilityAttribute,
    DeviceTrackerEntityStateAttribute,
    ScannerEntityStateAttribute,
    SourceType,
    TrackerEntityStateAttribute,
    TrackingType,
)

_LOGGER = logging.getLogger(__name__)


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


class BaseTrackerEntity(Entity):
    """Represent a tracked device.

    Not intended to be directly inherited by integrations. Integrations should
    inherit TrackerEntity, BaseScannerEntity or ScannerEntity instead.
    """

    _attr_device_info: None = None
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_source_type: SourceType

    @override
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Post initialisation processing."""
        super().__init_subclass__(**kwargs)
        if "battery_level" in cls.__dict__:
            if cls.__module__.startswith("homeassistant.components."):
                # Don't ask users to report issue for built in integrations,
                # they already have issues opened on them.
                return
            report_issue = async_suggest_report_issue(
                async_get_hass_or_none(), module=cls.__module__
            )
            _LOGGER.warning(
                (
                    "%s::%s is overriding the deprecated battery_level property on "
                    "a subclass of BaseTrackerEntity, this will be unsupported from "
                    "Home Assistant 2027.7, please %s"
                ),
                cls.__module__,
                cls.__name__,
                report_issue,
            )

    @cached_property
    def battery_level(self) -> int | None:
        """Return the battery level of the device.

        Percentage from 0-100.

        The property is deprecated and will be removed in Home Assistant 2027.7.
        """
        return None

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        if hasattr(self, "_attr_source_type"):
            return self._attr_source_type
        raise NotImplementedError

    @property
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attr: dict[str, Any] = {
            DeviceTrackerEntityStateAttribute.SOURCE_TYPE: self.source_type
        }

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
    _attr_capability_attributes: dict[str, Any] = {
        DeviceTrackerEntityCapabilityAttribute.TRACKING_TYPE: TrackingType.POSITION
    }
    _attr_in_zones: list[str] | None = None
    _attr_latitude: float | None = None
    _attr_location_accuracy: float = 0
    # _attr_location_name is deprecated and will be removed in Home Assistant 2027.7
    _attr_location_name: str | None = None
    _attr_longitude: float | None = None
    _attr_source_type: SourceType = SourceType.GPS

    __active_zone: State | None = None
    # If we reported setting deprecated _attr_location_name
    __deprecated_attr_location_name_reported = False
    __in_zones: list[str] | None = None

    @override
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Post initialisation processing."""
        super().__init_subclass__(**kwargs)
        if "location_name" in cls.__dict__:
            if cls.__module__.startswith("homeassistant.components."):
                # Don't ask users to report issue for built in integrations,
                # they already have issues opened on them.
                return
            report_issue = async_suggest_report_issue(
                async_get_hass_or_none(), module=cls.__module__
            )
            _LOGGER.warning(
                (
                    "%s::%s is overriding the deprecated location_name property on "
                    "an instance of TrackerEntity, this will be unsupported from "
                    "Home Assistant 2027.7, please %s"
                ),
                cls.__module__,
                cls.__name__,
                report_issue,
            )

    @cached_property
    @override
    def should_poll(self) -> bool:
        """No polling for entities that have location pushed."""
        return False

    @property
    @override
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
        """Return a location name for the current location of the device.

        The property is deprecated and will be removed in Home Assistant 2027.7.
        """
        if (location_name := self._attr_location_name) is not None:
            if (
                not self.__deprecated_attr_location_name_reported
                and not self.__class__.__module__.startswith(
                    "homeassistant.components."
                )
            ):
                report_issue = async_suggest_report_issue(
                    self.hass, module=self.__class__.__module__
                )
                _LOGGER.warning(
                    (
                        "%s::%s is setting the deprecated _attr_location_name attribute "
                        "on an instance of TrackerEntity, this will be unsupported from "
                        "Home Assistant 2027.7, please %s"
                    ),
                    self.__class__.__module__,
                    self.__class__.__name__,
                    report_issue,
                )
                self.__deprecated_attr_location_name_reported = True
            return location_name
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
    @override
    def _async_write_ha_state(self) -> None:
        """Calculate active zones and write the state."""
        self._async_update_zones()
        super()._async_write_ha_state()

    @callback
    @override
    def _async_calculate_state(self) -> CalculatedState:
        """Calculate active zones for state previews."""
        self._async_update_zones()
        return super()._async_calculate_state()

    @callback
    def _async_update_zones(self) -> None:
        """Calculate active zones."""
        if (zones := self.in_zones) is not None:
            zone_states = sorted(
                (
                    zone_state
                    for entity_id in zones
                    if (zone_state := self.hass.states.get(entity_id)) is not None
                ),
                key=lambda z: z.attributes[ZoneEntityStateAttribute.RADIUS],
            )
            self.__active_zone = next(
                (
                    z
                    for z in zone_states
                    if not z.attributes.get(ZoneEntityStateAttribute.PASSIVE)
                ),
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

    @property
    @override
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
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attr: dict[str, Any] = {
            DeviceTrackerEntityStateAttribute.IN_ZONES: self.__in_zones or []
        }
        attr.update(super().state_attributes)

        if self.latitude is not None and self.longitude is not None:
            attr[EntityStateAttribute.LATITUDE] = self.latitude
            attr[EntityStateAttribute.LONGITUDE] = self.longitude
            attr[TrackerEntityStateAttribute.GPS_ACCURACY] = self.location_accuracy

        return attr


class BaseScannerEntity(BaseTrackerEntity):
    """Base class for a tracked device that can be connected or disconnected.

    Unlike ScannerEntity, this entity does not make assumptions about MAC
    addresses being used to identify the device.
    """

    _attr_capability_attributes: dict[str, Any] = {
        DeviceTrackerEntityCapabilityAttribute.TRACKING_TYPE: TrackingType.CONNECTION
    }
    _scanner_option_associated_zone: str = zone.ENTITY_ID_HOME
    _scanner_option_associated_zone_unsub: CALLBACK_TYPE | None = None

    @override
    async def async_internal_added_to_hass(self) -> None:
        """Call when the scanner entity is added to hass."""
        await super().async_internal_added_to_hass()
        if not self.registry_entry:
            return
        self._async_read_entity_options()

    @override
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
    @override
    def async_internal_entity_id_changed(self, old_entity_id: str) -> None:
        """Refresh the entity_id shown by an open associated-zone repair issue."""
        super().async_internal_entity_id_changed(old_entity_id)
        if (
            ir.async_get(self.hass).async_get_issue(
                DOMAIN, self._associated_zone_issue_id
            )
            is not None
        ):
            self._async_create_associated_zone_issue()

    @callback
    @override
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
    @override
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
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attr: dict[str, Any] = {DeviceTrackerEntityStateAttribute.IN_ZONES: []}
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

        attr[DeviceTrackerEntityStateAttribute.IN_ZONES] = [
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
    _attr_device_info: DeviceInfo | None  # type: ignore[assignment]
    # Most scanned network clients are not worth tracking
    _attr_entity_registry_enabled_default = False
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
    @override
    def unique_id(self) -> str | None:
        """Return unique ID of the entity."""
        return self.mac_address

    @callback
    def _async_fallback_device_name(
        self, connections: set[tuple[str, str]]
    ) -> str | None:
        """Return the name of the tracked device for its default device info.

        The MAC address only names a new device, so it does not replace a name
        given by the integration's other entities or before the tracked device
        went offline.
        """
        if self.hostname:
            return self.hostname
        if TYPE_CHECKING:
            assert self.platform.config_entry is not None
        if dr.async_get(self.hass).async_get_devices(
            connections=connections,
            config_entry_id=self.platform.config_entry.entry_id,
        ):
            return None
        return self.mac_address

    @callback
    def _async_set_default_device_info(self) -> None:
        """Describe the tracked device for an integration which does not.

        To be removed in HA Core 2027.5, integrations should provide device info
        with the MAC address of the tracked device as a connection.
        """
        if TYPE_CHECKING:
            assert self.mac_address is not None
        connections = {(dr.CONNECTION_NETWORK_MAC, self.mac_address)}
        if (name := self._async_fallback_device_name(connections)) is None:
            self._attr_device_info = DeviceInfo(connections=connections)
        else:
            self._attr_device_info = DeviceInfo(connections=connections, name=name)

    @override
    async def async_prepare_to_add_to_hass(self) -> None:
        """Run before the entity is added to hass."""
        await super().async_prepare_to_add_to_hass()
        if (
            self.device_info is None
            and self.mac_address
            and self.unique_id
            and self.platform.config_entry is not None
        ):
            self._async_set_default_device_info()
        if (
            self.mac_address
            and self.unique_id
            and self.is_connected
            and self.ip_address
        ):
            _async_connected_device_registered(
                self.hass,
                self.mac_address,
                self.ip_address,
                self.hostname,
            )

    # BaseScannerEntity.state_attributes is @final to keep external subclasses
    # from tampering with it; ScannerEntity is an in-tree subclass that
    # intentionally extends it with ip/mac/hostname.
    @final  # type: ignore[misc]
    @property
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attr = super().state_attributes

        if ip_address := self.ip_address:
            attr[ScannerEntityStateAttribute.IP] = ip_address
        if (mac_address := self.mac_address) is not None:
            attr[ScannerEntityStateAttribute.MAC] = mac_address
        if (hostname := self.hostname) is not None:
            attr[ScannerEntityStateAttribute.HOST_NAME] = hostname

        return attr
