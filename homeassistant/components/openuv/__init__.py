"""Support for UV data from openuv.io."""
from __future__ import annotations

import asyncio
from typing import Any

from pyopenuv import Client
from pyopenuv.errors import OpenUvError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_BINARY_SENSORS,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SENSORS,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.service import verify_domain_control

from .const import (
    CONF_FROM_WINDOW,
    CONF_TO_WINDOW,
    DATA_PROTECTION_WINDOW,
    DATA_UV,
    DEFAULT_FROM_WINDOW,
    DEFAULT_TO_WINDOW,
    DOMAIN,
    LOGGER,
)

DEFAULT_ATTRIBUTION = "Data provided by OpenUV"

NOTIFICATION_ID = "openuv_notification"
NOTIFICATION_TITLE = "OpenUV Component Setup"

TOPIC_UPDATE = f"{DOMAIN}_data_update"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenUV as config entry."""
    _verify_domain_control = verify_domain_control(hass, DOMAIN)

    websession = aiohttp_client.async_get_clientsession(hass)
    openuv = OpenUV(
        entry,
        Client(
            entry.data[CONF_API_KEY],
            entry.data.get(CONF_LATITUDE, hass.config.latitude),
            entry.data.get(CONF_LONGITUDE, hass.config.longitude),
            altitude=entry.data.get(CONF_ELEVATION, hass.config.elevation),
            session=websession,
        ),
    )

    # We disable the client's request retry abilities here to avoid a lengthy (and
    # blocking) startup:
    openuv.client.disable_request_retries()

    try:
        await openuv.async_update()
    except HomeAssistantError as err:
        LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady from err

    # Once we've successfully authenticated, we re-enable client request retries:
    openuv.client.enable_request_retries()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = openuv

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    @_verify_domain_control
    async def update_data(_: ServiceCall) -> None:
        """Refresh all OpenUV data."""
        LOGGER.debug("Refreshing all OpenUV data")
        await openuv.async_update()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    @_verify_domain_control
    async def update_uv_index_data(_: ServiceCall) -> None:
        """Refresh OpenUV UV index data."""
        LOGGER.debug("Refreshing OpenUV UV index data")
        await openuv.async_update_uv_index_data()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    @_verify_domain_control
    async def update_protection_data(_: ServiceCall) -> None:
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an OpenUV config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate the config entry upon new versions."""
    version = entry.version
    data = {**entry.data}

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Remove unused condition data:
    if version == 1:
        data.pop(CONF_BINARY_SENSORS, None)
        data.pop(CONF_SENSORS, None)
        version = entry.version = 2
        hass.config_entries.async_update_entry(entry, data=data)
        LOGGER.debug("Migration to version %s successful", version)

    return True


class OpenUV:
    """Define a generic OpenUV object."""

    def __init__(self, entry: ConfigEntry, client: Client) -> None:
        """Initialize."""
        self._entry = entry
        self.client = client
        self.data: dict[str, Any] = {DATA_PROTECTION_WINDOW: {}, DATA_UV: {}}

    async def async_update_protection_data(self) -> None:
        """Update binary sensor (protection window) data."""
        low = self._entry.options.get(CONF_FROM_WINDOW, DEFAULT_FROM_WINDOW)
        high = self._entry.options.get(CONF_TO_WINDOW, DEFAULT_TO_WINDOW)

        try:
            data = await self.client.uv_protection_window(low=low, high=high)
        except OpenUvError as err:
            raise HomeAssistantError(
                f"Error during protection data update: {err}"
            ) from err

        self.data[DATA_PROTECTION_WINDOW] = data.get("result")

    async def async_update_uv_index_data(self) -> None:
        """Update sensor (uv index, etc) data."""
        try:
            data = await self.client.uv_index()
        except OpenUvError as err:
            raise HomeAssistantError(
                f"Error during UV index data update: {err}"
            ) from err

        self.data[DATA_UV] = data.get("result")

    async def async_update(self) -> None:
        """Update sensor/binary sensor data."""
        tasks = [self.async_update_protection_data(), self.async_update_uv_index_data()]
        await asyncio.gather(*tasks)


class OpenUvEntity(Entity):
    """Define a generic OpenUV entity."""

    def __init__(self, openuv: OpenUV, description: EntityDescription) -> None:
        """Initialize."""
        self._attr_extra_state_attributes = {}
        self._attr_should_poll = False
        self._attr_unique_id = (
            f"{openuv.client.latitude}_{openuv.client.longitude}_{description.key}"
        )
        self.entity_description = description
        self.openuv = openuv

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def update() -> None:
            """Update the state."""
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(async_dispatcher_connect(self.hass, TOPIC_UPDATE, update))

        self.update_from_latest_data()

    def update_from_latest_data(self) -> None:
        """Update the sensor using the latest data."""
        raise NotImplementedError
