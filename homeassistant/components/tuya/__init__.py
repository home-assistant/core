"""Support for Tuya Smart devices."""
import asyncio
from datetime import timedelta
import logging

from tuyaha import TuyaApi
from tuyaha.tuyaapi import TuyaAPIException, TuyaNetException, TuyaServerException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_COUNTRYCODE,
    DOMAIN,
    TUYA_DATA,
    TUYA_DISCOVERY_NEW,
    TUYA_PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

ENTRY_IS_SETUP = "tuya_entry_is_setup"

PARALLEL_UPDATES = 0

SERVICE_FORCE_UPDATE = "force_update"
SERVICE_PULL_DEVICES = "pull_devices"

SIGNAL_DELETE_ENTITY = "tuya_delete"
SIGNAL_UPDATE_ENTITY = "tuya_update"

TUYA_TYPE_TO_HA = {
    "climate": "climate",
    "cover": "cover",
    "fan": "fan",
    "light": "light",
    "scene": "scene",
    "switch": "switch",
}

TUYA_TRACKER = "tuya_tracker"

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_COUNTRYCODE): cv.string,
                    vol.Optional(CONF_PLATFORM, default="tuya"): cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Tuya integration."""

    conf = config.get(DOMAIN)
    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
            )
        )

    return True


async def async_setup_entry(hass, entry):
    """Set up Tuya platform."""

    tuya = TuyaApi()
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    country_code = entry.data[CONF_COUNTRYCODE]
    platform = entry.data[CONF_PLATFORM]

    try:
        await hass.async_add_executor_job(
            tuya.init, username, password, country_code, platform
        )
    except (TuyaNetException, TuyaServerException):
        raise ConfigEntryNotReady()

    except TuyaAPIException as exc:
        _LOGGER.error(
            "Connection error during integration setup. Error: %s", exc,
        )
        return False

    hass.data[DOMAIN] = {
        TUYA_DATA: tuya,
        TUYA_TRACKER: None,
        ENTRY_IS_SETUP: set(),
        "entities": {},
        "pending": {},
    }

    async def async_load_devices(device_list):
        """Load new devices by device_list."""
        device_type_list = {}
        for device in device_list:
            dev_type = device.device_type()
            if (
                dev_type in TUYA_TYPE_TO_HA
                and device.object_id() not in hass.data[DOMAIN]["entities"]
            ):
                ha_type = TUYA_TYPE_TO_HA[dev_type]
                if ha_type not in device_type_list:
                    device_type_list[ha_type] = []
                device_type_list[ha_type].append(device.object_id())
                hass.data[DOMAIN]["entities"][device.object_id()] = None

        for ha_type, dev_ids in device_type_list.items():
            config_entries_key = f"{ha_type}.tuya"
            if config_entries_key not in hass.data[DOMAIN][ENTRY_IS_SETUP]:
                hass.data[DOMAIN]["pending"][ha_type] = dev_ids
                hass.async_create_task(
                    hass.config_entries.async_forward_entry_setup(entry, ha_type)
                )
                hass.data[DOMAIN][ENTRY_IS_SETUP].add(config_entries_key)
            else:
                async_dispatcher_send(hass, TUYA_DISCOVERY_NEW.format(ha_type), dev_ids)

    device_list = await hass.async_add_executor_job(tuya.get_all_devices)
    await async_load_devices(device_list)

    def _get_updated_devices():
        tuya.poll_devices_update()
        return tuya.get_all_devices()

    async def async_poll_devices_update(event_time):
        """Check if accesstoken is expired and pull device list from server."""
        _LOGGER.debug("Pull devices from Tuya")
        # Add new discover device.
        device_list = await hass.async_add_executor_job(_get_updated_devices)
        await async_load_devices(device_list)
        # Delete not exist device.
        newlist_ids = []
        for device in device_list:
            newlist_ids.append(device.object_id())
        for dev_id in list(hass.data[DOMAIN]["entities"]):
            if dev_id not in newlist_ids:
                async_dispatcher_send(hass, SIGNAL_DELETE_ENTITY, dev_id)
                hass.data[DOMAIN]["entities"].pop(dev_id)

    hass.data[DOMAIN][TUYA_TRACKER] = async_track_time_interval(
        hass, async_poll_devices_update, timedelta(minutes=5)
    )

    hass.services.async_register(
        DOMAIN, SERVICE_PULL_DEVICES, async_poll_devices_update
    )

    async def async_force_update(call):
        """Force all devices to pull data."""
        async_dispatcher_send(hass, SIGNAL_UPDATE_ENTITY)

    hass.services.async_register(DOMAIN, SERVICE_FORCE_UPDATE, async_force_update)

    return True


async def async_unload_entry(hass, entry):
    """Unloading the Tuya platforms."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(
                    entry, component.split(".", 1)[0]
                )
                for component in hass.data[DOMAIN][ENTRY_IS_SETUP]
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][ENTRY_IS_SETUP] = set()
        hass.data[DOMAIN][TUYA_TRACKER]()
        hass.data[DOMAIN][TUYA_TRACKER] = None
        hass.data[DOMAIN][TUYA_DATA] = None
        hass.services.async_remove(DOMAIN, SERVICE_FORCE_UPDATE)
        hass.services.async_remove(DOMAIN, SERVICE_PULL_DEVICES)
        hass.data.pop(DOMAIN)

    return unload_ok


class TuyaDevice(Entity):
    """Tuya base device."""

    def __init__(self, tuya, platform):
        """Init Tuya devices."""
        self._tuya = tuya
        self._tuya_platform = platform

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        dev_id = self._tuya.object_id()
        self.hass.data[DOMAIN]["entities"][dev_id] = self.entity_id
        async_dispatcher_connect(self.hass, SIGNAL_DELETE_ENTITY, self._delete_callback)
        async_dispatcher_connect(self.hass, SIGNAL_UPDATE_ENTITY, self._update_callback)

    @property
    def object_id(self):
        """Return Tuya device id."""
        return self._tuya.object_id()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"tuya.{self._tuya.object_id()}"

    @property
    def name(self):
        """Return Tuya device name."""
        return self._tuya.name()

    @property
    def available(self):
        """Return if the device is available."""
        return self._tuya.available()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        _device_info = {
            "identifiers": {(DOMAIN, f"{self.unique_id}")},
            "manufacturer": TUYA_PLATFORMS.get(
                self._tuya_platform, self._tuya_platform
            ),
            "name": self.name,
            "model": self._tuya.object_type(),
        }
        return _device_info

    def update(self):
        """Refresh Tuya device data."""
        self._tuya.update()

    async def _delete_callback(self, dev_id):
        """Remove this entity."""
        if dev_id == self.object_id:
            entity_registry = (
                await self.hass.helpers.entity_registry.async_get_registry()
            )
            if entity_registry.async_is_registered(self.entity_id):
                entity_registry.async_remove(self.entity_id)
            else:
                await self.async_remove()

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)
