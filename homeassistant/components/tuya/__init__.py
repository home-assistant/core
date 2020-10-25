"""Support for Tuya Smart devices."""
import asyncio
from datetime import timedelta
import logging

from tuyaha import TuyaApi
from tuyaha.tuyaapi import (
    TuyaAPIException,
    TuyaFrequentlyInvokeException,
    TuyaNetException,
    TuyaServerException,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
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
    CONF_DISCOVERY_INTERVAL,
    CONF_QUERY_DEVICE,
    CONF_QUERY_INTERVAL,
    DEFAULT_DISCOVERY_INTERVAL,
    DEFAULT_QUERY_INTERVAL,
    DOMAIN,
    SIGNAL_CONFIG_ENTITY,
    SIGNAL_DELETE_ENTITY,
    SIGNAL_UPDATE_ENTITY,
    TUYA_DATA,
    TUYA_DEVICES_CONF,
    TUYA_DISCOVERY_NEW,
    TUYA_PLATFORMS,
    TUYA_TYPE_NOT_QUERY,
)

_LOGGER = logging.getLogger(__name__)

ATTR_TUYA_DEV_ID = "tuya_device_id"
ENTRY_IS_SETUP = "tuya_entry_is_setup"

SERVICE_FORCE_UPDATE = "force_update"
SERVICE_PULL_DEVICES = "pull_devices"

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
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_COUNTRYCODE): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(CONF_PLATFORM, default="tuya"): cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


def _update_discovery_interval(hass, interval):
    tuya = hass.data[DOMAIN].get(TUYA_DATA)
    if not tuya:
        return

    try:
        tuya.discovery_interval = interval
        _LOGGER.info("Tuya discovery device poll interval set to %s seconds", interval)
    except ValueError as ex:
        _LOGGER.warning(ex)


def _update_query_interval(hass, interval):
    tuya = hass.data[DOMAIN].get(TUYA_DATA)
    if not tuya:
        return

    try:
        tuya.query_interval = interval
        _LOGGER.info("Tuya query device poll interval set to %s seconds", interval)
    except ValueError as ex:
        _LOGGER.warning(ex)


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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
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
    except (
        TuyaNetException,
        TuyaServerException,
        TuyaFrequentlyInvokeException,
    ) as exc:
        raise ConfigEntryNotReady() from exc

    except TuyaAPIException as exc:
        _LOGGER.error(
            "Connection error during integration setup. Error: %s",
            exc,
        )
        return False

    hass.data[DOMAIN] = {
        TUYA_DATA: tuya,
        TUYA_DEVICES_CONF: entry.options.copy(),
        TUYA_TRACKER: None,
        ENTRY_IS_SETUP: set(),
        "entities": {},
        "pending": {},
        "listener": entry.add_update_listener(update_listener),
    }

    _update_discovery_interval(
        hass, entry.options.get(CONF_DISCOVERY_INTERVAL, DEFAULT_DISCOVERY_INTERVAL)
    )

    _update_query_interval(
        hass, entry.options.get(CONF_QUERY_INTERVAL, DEFAULT_QUERY_INTERVAL)
    )

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

    await async_load_devices(tuya.get_all_devices())

    def _get_updated_devices():
        try:
            tuya.poll_devices_update()
        except TuyaFrequentlyInvokeException as exc:
            _LOGGER.error(exc)
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
        hass, async_poll_devices_update, timedelta(minutes=2)
    )

    hass.services.async_register(
        DOMAIN, SERVICE_PULL_DEVICES, async_poll_devices_update
    )

    async def async_force_update(call):
        """Force all devices to pull data."""
        async_dispatcher_send(hass, SIGNAL_UPDATE_ENTITY)

    hass.services.async_register(DOMAIN, SERVICE_FORCE_UPDATE, async_force_update)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
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
        hass.data[DOMAIN]["listener"]()
        hass.data[DOMAIN][TUYA_TRACKER]()
        hass.services.async_remove(DOMAIN, SERVICE_FORCE_UPDATE)
        hass.services.async_remove(DOMAIN, SERVICE_PULL_DEVICES)
        hass.data.pop(DOMAIN)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Update when config_entry options update."""
    hass.data[DOMAIN][TUYA_DEVICES_CONF] = entry.options.copy()
    _update_discovery_interval(
        hass, entry.options.get(CONF_DISCOVERY_INTERVAL, DEFAULT_DISCOVERY_INTERVAL)
    )
    _update_query_interval(
        hass, entry.options.get(CONF_QUERY_INTERVAL, DEFAULT_QUERY_INTERVAL)
    )
    async_dispatcher_send(hass, SIGNAL_CONFIG_ENTITY)


async def cleanup_device_registry(hass: HomeAssistant, device_id):
    """Remove device registry entry if there are no remaining entities."""

    device_registry = await hass.helpers.device_registry.async_get_registry()
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    if device_id and not hass.helpers.entity_registry.async_entries_for_device(
        entity_registry, device_id
    ):
        device_registry.async_remove_device(device_id)


class TuyaDevice(Entity):
    """Tuya base device."""

    _dev_can_query_count = 0

    def __init__(self, tuya, platform):
        """Init Tuya devices."""
        self._tuya = tuya
        self._tuya_platform = platform

    def _device_can_query(self):
        """Check if device can also use query method."""
        dev_type = self._tuya.device_type()
        return dev_type not in TUYA_TYPE_NOT_QUERY

    def _inc_device_count(self):
        """Increment static variable device count."""
        if not self._device_can_query():
            return
        TuyaDevice._dev_can_query_count += 1

    def _dec_device_count(self):
        """Decrement static variable device count."""
        if not self._device_can_query():
            return
        TuyaDevice._dev_can_query_count -= 1

    def _get_device_config(self):
        """Get updated device options."""
        devices_config = self.hass.data[DOMAIN].get(TUYA_DEVICES_CONF)
        if not devices_config:
            return {}
        dev_conf = devices_config.get(self.object_id, {})
        if dev_conf:
            _LOGGER.debug(
                "Configuration for deviceID %s: %s", self.object_id, str(dev_conf)
            )
        return dev_conf

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]["entities"][self.object_id] = self.entity_id
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_DELETE_ENTITY, self._delete_callback
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_ENTITY, self._update_callback
            )
        )
        self._inc_device_count()

    async def async_will_remove_from_hass(self):
        """Call when entity is removed from hass."""
        self._dec_device_count()

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
        query_dev = self.hass.data[DOMAIN][TUYA_DEVICES_CONF].get(CONF_QUERY_DEVICE, "")
        use_discovery = (
            TuyaDevice._dev_can_query_count > 1 and self.object_id != query_dev
        )
        try:
            self._tuya.update(use_discovery=use_discovery)
        except TuyaFrequentlyInvokeException as exc:
            _LOGGER.error(exc)

    async def _delete_callback(self, dev_id):
        """Remove this entity."""
        if dev_id == self.object_id:
            entity_registry = (
                await self.hass.helpers.entity_registry.async_get_registry()
            )
            if entity_registry.async_is_registered(self.entity_id):
                entity_entry = entity_registry.async_get(self.entity_id)
                entity_registry.async_remove(self.entity_id)
                await cleanup_device_registry(self.hass, entity_entry.device_id)
            else:
                await self.async_remove()

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)
