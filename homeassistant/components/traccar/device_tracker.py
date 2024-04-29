"""Support for Traccar device tracking."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pytraccar import ApiClient, TraccarException
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    SourceType,
    TrackerEntity,
)
from homeassistant.components.device_tracker.legacy import (
    YAML_DEVICES,
    remove_device_from_config,
)
from homeassistant.config import load_yaml_config_file
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_EVENT,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    Event,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from . import DOMAIN, TRACKER_UPDATE
from .const import (
    ATTR_ACCURACY,
    ATTR_ALTITUDE,
    ATTR_BATTERY,
    ATTR_BEARING,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_SPEED,
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

    hass.data[DOMAIN]["unsub_device_tracker"][entry.entry_id] = (
        async_dispatcher_connect(hass, TRACKER_UPDATE, _receive_data)
    )

    # Restore previously loaded devices
    dev_reg = dr.async_get(hass)
    dev_ids = {
        identifier[1]
        for device in dev_reg.devices.get_devices_for_config_entry_id(entry.entry_id)
        for identifier in device.identifiers
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
    """Import configuration to the new integration."""
    api = ApiClient(
        host=config[CONF_HOST],
        port=config[CONF_PORT],
        ssl=config[CONF_SSL],
        username=config[CONF_USERNAME],
        password=config[CONF_PASSWORD],
        client_session=async_get_clientsession(hass, config[CONF_VERIFY_SSL]),
    )

    async def _run_import(_: Event):
        known_devices: dict[str, dict[str, Any]] = {}
        try:
            known_devices = await hass.async_add_executor_job(
                load_yaml_config_file, hass.config.path(YAML_DEVICES)
            )
        except (FileNotFoundError, HomeAssistantError):
            _LOGGER.debug(
                "No valid known_devices.yaml found, "
                "skip removal of devices from known_devices.yaml"
            )

        if known_devices:
            traccar_devices: list[str] = []
            try:
                resp = await api.get_devices()
                traccar_devices = [slugify(device["name"]) for device in resp]
            except TraccarException as exception:
                _LOGGER.error("Error while getting device data: %s", exception)
                return

            for dev_name in traccar_devices:
                if dev_name in known_devices:
                    await hass.async_add_executor_job(
                        remove_device_from_config, hass, dev_name
                    )
                    _LOGGER.debug("Removed device %s from known_devices.yaml", dev_name)

                if not hass.states.async_available(f"device_tracker.{dev_name}"):
                    hass.states.async_remove(f"device_tracker.{dev_name}")

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                "traccar_server",
                context={"source": SOURCE_IMPORT},
                data=config,
            )
        )

        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.8.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Traccar",
            },
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _run_import)
    return True


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
