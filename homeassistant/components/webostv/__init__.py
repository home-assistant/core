"""Support for LG webOS Smart TV."""

from __future__ import annotations

from contextlib import suppress
import logging

from aiowebostv import WebOsClient, WebOsTvPairError

from homeassistant.components import notify as hass_notify
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_SECRET,
    CONF_HOST,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    DATA_HASS_CONFIG,
    DOMAIN,
    PLATFORMS,
    WEBOSTV_EXCEPTIONS,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


_LOGGER = logging.getLogger(__name__)

type WebOsTvConfigEntry = ConfigEntry[WebOsClient]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LG WebOS TV platform."""
    hass.data.setdefault(DOMAIN, {DATA_HASS_CONFIG: config})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: WebOsTvConfigEntry) -> bool:
    """Set the config entry up."""
    host = entry.data[CONF_HOST]
    key = entry.data[CONF_CLIENT_SECRET]

    # Attempt a connection, but fail gracefully if tv is off for example.
    entry.runtime_data = client = WebOsClient(host, key)
    with suppress(*WEBOSTV_EXCEPTIONS):
        try:
            await client.connect()
        except WebOsTvPairError as err:
            raise ConfigEntryAuthFailed(err) from err

    # If pairing request accepted there will be no error
    # Update the stored key without triggering reauth
    update_client_key(hass, entry, client)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # set up notify platform, no entry support for notify component yet,
    # have to use discovery to load platform.
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                CONF_NAME: entry.title,
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            },
            hass.data[DOMAIN][DATA_HASS_CONFIG],
        )
    )

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    async def async_on_stop(_event: Event) -> None:
        """Unregister callbacks and disconnect."""
        client.clear_state_update_callbacks()
        await client.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_on_stop)
    )
    return True


async def async_update_options(hass: HomeAssistant, entry: WebOsTvConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_control_connect(host: str, key: str | None) -> WebOsClient:
    """LG Connection."""
    client = WebOsClient(host, key)
    try:
        await client.connect()
    except WebOsTvPairError:
        _LOGGER.warning("Connected to LG webOS TV %s but not paired", host)
        raise

    return client


def update_client_key(
    hass: HomeAssistant, entry: ConfigEntry, client: WebOsClient
) -> None:
    """Check and update stored client key if key has changed."""
    host = entry.data[CONF_HOST]
    key = entry.data[CONF_CLIENT_SECRET]

    if client.client_key != key:
        _LOGGER.debug("Updating client key for host %s", host)
        data = {CONF_HOST: host, CONF_CLIENT_SECRET: client.client_key}
        hass.config_entries.async_update_entry(entry, data=data)


async def async_unload_entry(hass: HomeAssistant, entry: WebOsTvConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        client = entry.runtime_data
        await hass_notify.async_reload(hass, DOMAIN)
        client.clear_state_update_callbacks()
        await client.disconnect()

    return unload_ok
