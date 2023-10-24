"""Support for Traccar device tracking."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from pytraccar import (
    ApiClient,
    DeviceModel,
    GeofenceModel,
    PositionModel,
    TraccarAuthenticationException,
    TraccarConnectionException,
    TraccarException,
)
from stringcase import camelcase
import voluptuous as vol

from homeassistant.components.device_tracker import (
    CONF_SCAN_INTERVAL,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    SourceType,
    TrackerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_EVENT,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util, slugify

from . import DOMAIN, TRACKER_UPDATE
from .const import (
    ATTR_ACCURACY,
    ATTR_ADDRESS,
    ATTR_ALTITUDE,
    ATTR_BATTERY,
    ATTR_BEARING,
    ATTR_CATEGORY,
    ATTR_GEOFENCE,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MOTION,
    ATTR_SPEED,
    ATTR_STATUS,
    ATTR_TRACCAR_ID,
    ATTR_TRACKER,
    CONF_MAX_ACCURACY,
    CONF_SKIP_ACCURACY_ON,
    EVENT_ALARM,
    EVENT_ALL_EVENTS,
    EVENT_COMMAND_RESULT,
    EVENT_DEVICE_FUEL_DROP,
    EVENT_DEVICE_MOVING,
    EVENT_DEVICE_OFFLINE,
    EVENT_DEVICE_ONLINE,
    EVENT_DEVICE_OVERSPEED,
    EVENT_DEVICE_STOPPED,
    EVENT_DEVICE_UNKNOWN,
    EVENT_DRIVER_CHANGED,
    EVENT_GEOFENCE_ENTER,
    EVENT_GEOFENCE_EXIT,
    EVENT_IGNITION_OFF,
    EVENT_IGNITION_ON,
    EVENT_MAINTENANCE,
    EVENT_TEXT_MESSAGE,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
SCAN_INTERVAL = DEFAULT_SCAN_INTERVAL

EVENTS = [
    EVENT_DEVICE_MOVING,
    EVENT_COMMAND_RESULT,
    EVENT_DEVICE_FUEL_DROP,
    EVENT_GEOFENCE_ENTER,
    EVENT_DEVICE_OFFLINE,
    EVENT_DRIVER_CHANGED,
    EVENT_GEOFENCE_EXIT,
    EVENT_DEVICE_OVERSPEED,
    EVENT_DEVICE_ONLINE,
    EVENT_DEVICE_STOPPED,
    EVENT_MAINTENANCE,
    EVENT_ALARM,
    EVENT_TEXT_MESSAGE,
    EVENT_DEVICE_UNKNOWN,
    EVENT_IGNITION_OFF,
    EVENT_IGNITION_ON,
    EVENT_ALL_EVENTS,
]

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=8082): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Required(CONF_MAX_ACCURACY, default=0): cv.positive_int,
        vol.Optional(CONF_SKIP_ACCURACY_ON, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_EVENT, default=[]): vol.All(
            cv.ensure_list,
            [vol.In(EVENTS)],
        ),
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Configure a dispatcher connection based on a config entry."""

    @callback
    def _receive_data(device, latitude, longitude, battery, accuracy, attrs):
        """Receive set location."""
        if device in hass.data[DOMAIN]["devices"]:
            return

        hass.data[DOMAIN]["devices"].add(device)

        async_add_entities(
            [TraccarEntity(device, latitude, longitude, battery, accuracy, attrs)]
        )

    hass.data[DOMAIN]["unsub_device_tracker"][
        entry.entry_id
    ] = async_dispatcher_connect(hass, TRACKER_UPDATE, _receive_data)

    # Restore previously loaded devices
    dev_reg = dr.async_get(hass)
    dev_ids = {
        identifier[1]
        for device in dev_reg.devices.values()
        for identifier in device.identifiers
        if identifier[0] == DOMAIN
    }
    if not dev_ids:
        return

    entities = []
    for dev_id in dev_ids:
        hass.data[DOMAIN]["devices"].add(dev_id)
        entity = TraccarEntity(dev_id, None, None, None, None, None)
        entities.append(entity)

    async_add_entities(entities)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Validate the configuration and return a Traccar scanner."""
    api = ApiClient(
        host=config[CONF_HOST],
        port=config[CONF_PORT],
        ssl=config[CONF_SSL],
        username=config[CONF_USERNAME],
        password=config[CONF_PASSWORD],
        client_session=async_get_clientsession(hass, config[CONF_VERIFY_SSL]),
    )

    scanner = TraccarScanner(
        api,
        hass,
        async_see,
        config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL),
        config[CONF_MAX_ACCURACY],
        config[CONF_SKIP_ACCURACY_ON],
        config[CONF_MONITORED_CONDITIONS],
        config[CONF_EVENT],
    )

    return await scanner.async_init()


class TraccarScanner:
    """Define an object to retrieve Traccar data."""

    def __init__(
        self,
        api: ApiClient,
        hass: HomeAssistant,
        async_see: AsyncSeeCallback,
        scan_interval: timedelta,
        max_accuracy: int,
        skip_accuracy_on: bool,
        custom_attributes: list[str],
        event_types: list[str],
    ) -> None:
        """Initialize."""

        if EVENT_ALL_EVENTS in event_types:
            event_types = EVENTS
        self._event_types = {camelcase(evt): evt for evt in event_types}
        self._custom_attributes = custom_attributes
        self._scan_interval = scan_interval
        self._async_see = async_see
        self._api = api
        self._hass = hass
        self._max_accuracy = max_accuracy
        self._skip_accuracy_on = skip_accuracy_on
        self._devices: list[DeviceModel] = []
        self._positions: list[PositionModel] = []
        self._geofences: list[GeofenceModel] = []

    async def async_init(self):
        """Further initialize connection to Traccar."""
        try:
            await self._api.get_server()
        except TraccarAuthenticationException:
            _LOGGER.error("Authentication for Traccar failed")
            return False
        except TraccarConnectionException as exception:
            _LOGGER.error("Connection with Traccar failed - %s", exception)
            return False

        await self._async_update()
        async_track_time_interval(
            self._hass, self._async_update, self._scan_interval, cancel_on_shutdown=True
        )
        return True

    async def _async_update(self, now=None):
        """Update info from Traccar."""
        _LOGGER.debug("Updating device data")
        try:
            (
                self._devices,
                self._positions,
                self._geofences,
            ) = await asyncio.gather(
                self._api.get_devices(),
                self._api.get_positions(),
                self._api.get_geofences(),
            )
        except TraccarException as ex:
            _LOGGER.error("Error while updating device data: %s", ex)
            return

        self._hass.async_create_task(self.import_device_data())
        if self._event_types:
            self._hass.async_create_task(self.import_events())

    async def import_device_data(self):
        """Import device data from Traccar."""
        for position in self._positions:
            device = next(
                (dev for dev in self._devices if dev.id == position.device_id), None
            )

            if not device:
                continue

            attr = {
                ATTR_TRACKER: "traccar",
                ATTR_ADDRESS: position.address,
                ATTR_SPEED: position.speed,
                ATTR_ALTITUDE: position.altitude,
                ATTR_MOTION: position.attributes.get("motion", False),
                ATTR_TRACCAR_ID: device.id,
                ATTR_GEOFENCE: next(
                    (
                        geofence.name
                        for geofence in self._geofences
                        if geofence.id in (device.geofence_ids or [])
                    ),
                    None,
                ),
                ATTR_CATEGORY: device.category,
                ATTR_STATUS: device.status,
            }

            skip_accuracy_filter = False

            for custom_attr in self._custom_attributes:
                if device.attributes.get(custom_attr) is not None:
                    attr[custom_attr] = position.attributes[custom_attr]
                    if custom_attr in self._skip_accuracy_on:
                        skip_accuracy_filter = True
                if position.attributes.get(custom_attr) is not None:
                    attr[custom_attr] = position.attributes[custom_attr]
                    if custom_attr in self._skip_accuracy_on:
                        skip_accuracy_filter = True

            accuracy = position.accuracy or 0.0
            if (
                not skip_accuracy_filter
                and self._max_accuracy > 0
                and accuracy > self._max_accuracy
            ):
                _LOGGER.debug(
                    "Excluded position by accuracy filter: %f (%s)",
                    accuracy,
                    attr[ATTR_TRACCAR_ID],
                )
                continue

            await self._async_see(
                dev_id=slugify(device.name),
                gps=(position.latitude, position.longitude),
                gps_accuracy=accuracy,
                battery=position.attributes.get("batteryLevel", -1),
                attributes=attr,
            )

    async def import_events(self):
        """Import events from Traccar."""
        # get_reports_events requires naive UTC datetimes as of 1.0.0
        start_intervel = dt_util.utcnow().replace(tzinfo=None)
        events = await self._api.get_reports_events(
            devices=[device.id for device in self._devices],
            start_time=start_intervel,
            end_time=start_intervel - self._scan_interval,
            event_types=self._event_types.keys(),
        )
        if events is not None:
            for event in events:
                self._hass.bus.async_fire(
                    f"traccar_{self._event_types.get(event.type)}",
                    {
                        "device_traccar_id": event.device_id,
                        "device_name": next(
                            (
                                dev.name
                                for dev in self._devices
                                if dev.id == event.device_id
                            ),
                            None,
                        ),
                        "type": event.type,
                        "serverTime": event.event_time,
                        "attributes": event.attributes,
                    },
                )


class TraccarEntity(TrackerEntity, RestoreEntity):
    """Represent a tracked device."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device, latitude, longitude, battery, accuracy, attributes):
        """Set up Traccar entity."""
        self._accuracy = accuracy
        self._attributes = attributes
        self._name = device
        self._battery = battery
        self._latitude = latitude
        self._longitude = longitude
        self._unsub_dispatcher = None
        self._unique_id = device

    @property
    def battery_level(self):
        """Return battery value of the device."""
        return self._battery

    @property
    def extra_state_attributes(self):
        """Return device specific attributes."""
        return self._attributes

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._latitude

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._longitude

    @property
    def location_accuracy(self):
        """Return the gps accuracy of the device."""
        return self._accuracy

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            name=self._name,
            identifiers={(DOMAIN, self._unique_id)},
        )

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        await super().async_added_to_hass()
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self._async_receive_data
        )

        # don't restore if we got created with data
        if self._latitude is not None or self._longitude is not None:
            return

        if (state := await self.async_get_last_state()) is None:
            self._latitude = None
            self._longitude = None
            self._accuracy = None
            self._attributes = {
                ATTR_ALTITUDE: None,
                ATTR_BEARING: None,
                ATTR_SPEED: None,
            }
            self._battery = None
            return

        attr = state.attributes
        self._latitude = attr.get(ATTR_LATITUDE)
        self._longitude = attr.get(ATTR_LONGITUDE)
        self._accuracy = attr.get(ATTR_ACCURACY)
        self._attributes = {
            ATTR_ALTITUDE: attr.get(ATTR_ALTITUDE),
            ATTR_BEARING: attr.get(ATTR_BEARING),
            ATTR_SPEED: attr.get(ATTR_SPEED),
        }
        self._battery = attr.get(ATTR_BATTERY)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up after entity before removal."""
        await super().async_will_remove_from_hass()
        self._unsub_dispatcher()

    @callback
    def _async_receive_data(
        self, device, latitude, longitude, battery, accuracy, attributes
    ):
        """Mark the device as seen."""
        if device != self._name:
            return

        self._latitude = latitude
        self._longitude = longitude
        self._battery = battery
        self._accuracy = accuracy
        self._attributes.update(attributes)
        self.async_write_ha_state()
