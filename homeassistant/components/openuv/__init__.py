"""Support for UV data from openuv.io."""
import asyncio

from pyopenuv import Client
from pyopenuv.errors import OpenUvError

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_BINARY_SENSORS,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SENSORS,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.service import verify_domain_control

from .const import (
    DATA_CLIENT,
    DATA_LISTENER,
    DATA_PROTECTION_WINDOW,
    DATA_UV,
    DOMAIN,
    LOGGER,
)

DEFAULT_ATTRIBUTION = "Data provided by OpenUV"

NOTIFICATION_ID = "openuv_notification"
NOTIFICATION_TITLE = "OpenUV Component Setup"

TOPIC_UPDATE = f"{DOMAIN}_data_update"

PLATFORMS = ["binary_sensor", "sensor"]


async def async_setup(hass, config):
    """Set up the OpenUV component."""
    hass.data[DOMAIN] = {DATA_CLIENT: {}, DATA_LISTENER: {}}
    return True


async def async_setup_entry(hass, config_entry):
    """Set up OpenUV as config entry."""
    _verify_domain_control = verify_domain_control(hass, DOMAIN)

    try:
        websession = aiohttp_client.async_get_clientsession(hass)
        openuv = OpenUV(
            Client(
                config_entry.data[CONF_API_KEY],
                config_entry.data.get(CONF_LATITUDE, hass.config.latitude),
                config_entry.data.get(CONF_LONGITUDE, hass.config.longitude),
                websession,
                altitude=config_entry.data.get(CONF_ELEVATION, hass.config.elevation),
            )
        )
        await openuv.async_update()
        hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = openuv
    except OpenUvError as err:
        LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady from err

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    @_verify_domain_control
    async def update_data(service):
        """Refresh all OpenUV data."""
        LOGGER.debug("Refreshing all OpenUV data")
        await openuv.async_update()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    @_verify_domain_control
    async def update_uv_index_data(service):
        """Refresh OpenUV UV index data."""
        LOGGER.debug("Refreshing OpenUV UV index data")
        await openuv.async_update_uv_index_data()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    @_verify_domain_control
    async def update_protection_data(service):
        """Refresh OpenUV protection window data."""
        LOGGER.debug("Refreshing OpenUV protection window data")
        await openuv.async_update_protection_data()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    for service, method in (
        ("update_data", update_data),
        ("update_uv_index_data", update_uv_index_data),
        ("update_protection_data", update_protection_data),
    ):
        hass.services.async_register(DOMAIN, service, method)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an OpenUV config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass, config_entry):
    """Migrate the config entry upon new versions."""
    version = config_entry.version
    data = {**config_entry.data}

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Remove unused condition data:
    if version == 1:
        data.pop(CONF_BINARY_SENSORS, None)
        data.pop(CONF_SENSORS, None)
        version = config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=data)
        LOGGER.debug("Migration to version %s successful", version)

    return True


class OpenUV:
    """Define a generic OpenUV object."""

    def __init__(self, client):
        """Initialize."""
        self.client = client
        self.data = {}

    async def async_update_protection_data(self):
        """Update binary sensor (protection window) data."""
        try:
            resp = await self.client.uv_protection_window()
            self.data[DATA_PROTECTION_WINDOW] = resp["result"]
        except OpenUvError as err:
            LOGGER.error("Error during protection data update: %s", err)
            self.data[DATA_PROTECTION_WINDOW] = {}

    async def async_update_uv_index_data(self):
        """Update sensor (uv index, etc) data."""
        try:
            data = await self.client.uv_index()
            self.data[DATA_UV] = data
        except OpenUvError as err:
            LOGGER.error("Error during uv index data update: %s", err)
            self.data[DATA_UV] = {}

    async def async_update(self):
        """Update sensor/binary sensor data."""
        tasks = [self.async_update_protection_data(), self.async_update_uv_index_data()]
        await asyncio.gather(*tasks)


class OpenUvEntity(Entity):
    """Define a generic OpenUV entity."""

    def __init__(self, openuv, sensor_type):
        """Initialize."""
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._attr_should_poll = False
        self._attr_unique_id = (
            f"{openuv.client.latitude}_{openuv.client.longitude}_{sensor_type}"
        )
        self._sensor_type = sensor_type
        self.openuv = openuv

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(async_dispatcher_connect(self.hass, TOPIC_UPDATE, update))

        self.update_from_latest_data()

    def update_from_latest_data(self):
        """Update the sensor using the latest data."""
        raise NotImplementedError
