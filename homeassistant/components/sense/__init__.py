"""Support for monitoring a Sense energy sensor."""
import asyncio
from datetime import timedelta
from time import time
import logging

from sense_energy import (
    ASyncSenseable,
    PlugInstance,
    SenseAPITimeoutException,
    SenseAuthenticationException,
    SenseLink,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_EMAIL,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TIMEOUT,
)
import homeassistant.components as comps
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ACTIVE_UPDATE_RATE,
    CONF_POWER,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SENSE_DATA,
    SENSE_DEVICE_UPDATE,
    SENSE_DEVICES_DATA,
    SENSE_DISCOVERED_DEVICES_DATA,
    SENSE_LINK,
    SENSE_TIMEOUT_EXCEPTIONS,
    SENSE_TRENDS_COORDINATOR,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor"]

CONFIG_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_POWER): vol.Any(vol.Coerce(float), cv.template,),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_EMAIL): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
                vol.Optional(CONF_ENTITIES): vol.Schema(
                    {cv.entity_id: CONFIG_ENTITY_SCHEMA}
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class SenseDevicesData:
    """Data for each sense device."""

    def __init__(self):
        """Create."""
        self._data_by_device = {}

    def set_devices_data(self, devices):
        """Store a device update."""
        self._data_by_device = {}
        for device in devices:
            self._data_by_device[device["id"]] = device

    def get_device_by_id(self, sense_device_id):
        """Get the latest device data."""
        return self._data_by_device.get(sense_device_id)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Sense component."""
    hass.data.setdefault(DOMAIN, {})
    conf = config.get(DOMAIN)
    if not conf:
        return True
    hass.data[DOMAIN][CONF_ENTITIES] = conf.get(CONF_ENTITIES, {})

    def devices():
        """Drvices to be emulated."""
        yield from get_plug_devices(hass)

    hass.data[DOMAIN][SENSE_LINK] = SenseLink(devices())
    if hass.data[DOMAIN][CONF_ENTITIES]:
        await hass.data[DOMAIN][SENSE_LINK].start()

    if not conf.get(CONF_EMAIL) or not conf.get(CONF_PASSWORD):
        return True
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_EMAIL: conf[CONF_EMAIL], CONF_PASSWORD: conf[CONF_PASSWORD],},
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Sense from a config entry."""

    entry_data = entry.data
    email = entry_data[CONF_EMAIL]
    password = entry_data[CONF_PASSWORD]
    timeout = entry_data[CONF_TIMEOUT]

    gateway = ASyncSenseable(api_timeout=timeout, wss_timeout=timeout)
    gateway.rate_limit = ACTIVE_UPDATE_RATE

    try:
        await gateway.authenticate(email, password)
    except SenseAuthenticationException:
        _LOGGER.error("Could not authenticate with sense server")
        return False
    except SENSE_TIMEOUT_EXCEPTIONS:
        raise ConfigEntryNotReady

    sense_devices_data = SenseDevicesData()
    try:
        sense_discovered_devices = await gateway.get_discovered_device_data()
    except SENSE_TIMEOUT_EXCEPTIONS:
        raise ConfigEntryNotReady

    trends_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Sense Trends {email}",
        update_method=gateway.update_trend_data,
        update_interval=timedelta(seconds=300),
    )

    # This can take longer than 60s and we already know
    # sense is online since get_discovered_device_data was
    # successful so we do it later.
    hass.loop.create_task(trends_coordinator.async_request_refresh())

    hass.data[DOMAIN][entry.entry_id] = {
        SENSE_DATA: gateway,
        SENSE_DEVICES_DATA: sense_devices_data,
        SENSE_TRENDS_COORDINATOR: trends_coordinator,
        SENSE_DISCOVERED_DEVICES_DATA: sense_discovered_devices,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    async def async_sense_update(_):
        """Retrieve latest state."""
        try:
            await gateway.update_realtime()
        except SenseAPITimeoutException:
            _LOGGER.error("Timeout retrieving data")

        data = gateway.get_realtime()
        if "devices" in data:
            sense_devices_data.set_devices_data(data["devices"])
        async_dispatcher_send(hass, f"{SENSE_DEVICE_UPDATE}-{gateway.sense_monitor_id}")

    hass.data[DOMAIN][entry.entry_id][
        "track_time_remove_callback"
    ] = async_track_time_interval(
        hass, async_sense_update, timedelta(seconds=ACTIVE_UPDATE_RATE)
    )
    return True


def get_plug_devices(hass):
    """Produced list of plug devices from config entities."""
    entities = hass.data[DOMAIN][CONF_ENTITIES]
    for entity_id in entities:
        state = hass.states.get(entity_id)
        if state is None:
            continue
        name = state.attributes.get(ATTR_FRIENDLY_NAME, entity_id)
        name = entities[entity_id].get(CONF_NAME, name)

        if comps.is_on(hass, entity_id):
            try:
                power = float(entities[entity_id][CONF_POWER])
            except TypeError:
                entities[entity_id][CONF_POWER].hass = hass
                power = float(entities[entity_id][CONF_POWER].async_render())

            if state.last_changed:
                last_changed = state.last_changed.timestamp()
            else:
                last_changed = time() - 1
        else:
            power = 0.0
            last_changed = time()
        yield PlugInstance(entity_id, start_time=last_changed, alias=name, power=power)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    track_time_remove_callback = hass.data[DOMAIN][entry.entry_id][
        "track_time_remove_callback"
    ]
    track_time_remove_callback()

    await hass.data[DOMAIN][SENSE_LINK].stop()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
