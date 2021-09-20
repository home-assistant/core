"""Support for Traccar device tracking."""
from datetime import datetime, timedelta
import logging

from pytraccar.api import API
from stringcase import camelcase
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SOURCE_TYPE_GPS,
)
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_EVENT,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify

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
            [
                vol.Any(
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
                )
            ],
        ),
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
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
    dev_reg = await device_registry.async_get_registry(hass)
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


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Validate the configuration and return a Traccar scanner."""

    session = async_get_clientsession(hass, config[CONF_VERIFY_SSL])

    api = API(
        hass.loop,
        session,
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        config[CONF_HOST],
        config[CONF_PORT],
        config[CONF_SSL],
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
        api,
        hass,
        async_see,
        scan_interval,
        max_accuracy,
        skip_accuracy_on,
        custom_attributes,
        event_types,
    ):
        """Initialize."""

        self._event_types = {camelcase(evt): evt for evt in event_types}
        self._custom_attributes = custom_attributes
        self._scan_interval = scan_interval
        self._async_see = async_see
        self._api = api
        self.connected = False
        self._hass = hass
        self._max_accuracy = max_accuracy
        self._skip_accuracy_on = skip_accuracy_on

    async def async_init(self):
        """Further initialize connection to Traccar."""
        await self._api.test_connection()
        if self._api.connected and not self._api.authenticated:
            _LOGGER.error("Authentication for Traccar failed")
            return False

        await self._async_update()
        async_track_time_interval(self._hass, self._async_update, self._scan_interval)
        return True

    async def _async_update(self, now=None):
        """Update info from Traccar."""
        if not self.connected:
            _LOGGER.debug("Testing connection to Traccar")
            await self._api.test_connection()
            self.connected = self._api.connected
            if self.connected:
                _LOGGER.info("Connection to Traccar restored")
            else:
                return
        _LOGGER.debug("Updating device data")
        await self._api.get_device_info(self._custom_attributes)
        self._hass.async_create_task(self.import_device_data())
        if self._event_types:
            self._hass.async_create_task(self.import_events())
        self.connected = self._api.connected

    async def import_device_data(self):
        """Import device data from Traccar."""
        for device_unique_id in self._api.device_info:
            device_info = self._api.device_info[device_unique_id]
            device = None
            attr = {}
            skip_accuracy_filter = False

            attr[ATTR_TRACKER] = "traccar"
            if device_info.get("address") is not None:
                attr[ATTR_ADDRESS] = device_info["address"]
            if device_info.get("geofence") is not None:
                attr[ATTR_GEOFENCE] = device_info["geofence"]
            if device_info.get("category") is not None:
                attr[ATTR_CATEGORY] = device_info["category"]
            if device_info.get("speed") is not None:
                attr[ATTR_SPEED] = device_info["speed"]
            if device_info.get("motion") is not None:
                attr[ATTR_MOTION] = device_info["motion"]
            if device_info.get("traccar_id") is not None:
                attr[ATTR_TRACCAR_ID] = device_info["traccar_id"]
                for dev in self._api.devices:
                    if dev["id"] == device_info["traccar_id"]:
                        device = dev
                        break
            if device is not None and device.get("status") is not None:
                attr[ATTR_STATUS] = device["status"]
            for custom_attr in self._custom_attributes:
                if device_info.get(custom_attr) is not None:
                    attr[custom_attr] = device_info[custom_attr]
                    if custom_attr in self._skip_accuracy_on:
                        skip_accuracy_filter = True

            accuracy = 0.0
            if device_info.get("accuracy") is not None:
                accuracy = device_info["accuracy"]
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
                dev_id=slugify(device_info["device_id"]),
                gps=(device_info.get("latitude"), device_info.get("longitude")),
                gps_accuracy=accuracy,
                battery=device_info.get("battery"),
                attributes=attr,
            )

    async def import_events(self):
        """Import events from Traccar."""
        device_ids = [device["id"] for device in self._api.devices]
        end_interval = datetime.utcnow()
        start_interval = end_interval - self._scan_interval
        events = await self._api.get_events(
            device_ids=device_ids,
            from_time=start_interval,
            to_time=end_interval,
            event_types=self._event_types.keys(),
        )
        if events is not None:
            for event in events:
                device_name = next(
                    (
                        dev.get("name")
                        for dev in self._api.devices
                        if dev.get("id") == event["deviceId"]
                    ),
                    None,
                )
                self._hass.bus.async_fire(
                    f"traccar_{self._event_types.get(event['type'])}",
                    {
                        "device_traccar_id": event["deviceId"],
                        "device_name": device_name,
                        "type": event["type"],
                        "serverTime": event["serverTime"],
                        "attributes": event["attributes"],
                    },
                )


class TraccarEntity(TrackerEntity, RestoreEntity):
    """Represent a tracked device."""

    def __init__(self, device, latitude, longitude, battery, accuracy, attributes):
        """Set up Geofency entity."""
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
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {"name": self._name, "identifiers": {(DOMAIN, self._unique_id)}}

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    async def async_added_to_hass(self):
        """Register state update callback."""
        await super().async_added_to_hass()
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self._async_receive_data
        )

        # don't restore if we got created with data
        if self._latitude is not None or self._longitude is not None:
            return

        state = await self.async_get_last_state()
        if state is None:
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

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        await super().async_will_remove_from_hass()
        self._unsub_dispatcher()

    @callback
    def _async_receive_data(
        self, device, latitude, longitude, battery, accuracy, attributes
    ):
        """Mark the device as seen."""
        if device != self.name:
            return

        self._latitude = latitude
        self._longitude = longitude
        self._battery = battery
        self._accuracy = accuracy
        self._attributes.update(attributes)
        self.async_write_ha_state()
